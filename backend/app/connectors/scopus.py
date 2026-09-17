"""
Scopus / Elsevier API connector.

Uses:
- Scopus Search API: discover publications by author name + affiliation.
- Scopus Author Search: resolve faculty → Scopus Author IDs.
- Scopus Abstract Retrieval: enrich journal-level metadata (quartile, SJR).

All calls are gated behind a valid SCOPUS_API_KEY.
"""

import httpx
import logging
import asyncio
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class ScopusClient:
    """Client for Elsevier Scopus APIs."""

    SEARCH_URL = "https://api.elsevier.com/content/search/scopus"
    AUTHOR_SEARCH_URL = "https://api.elsevier.com/content/search/author"
    ABSTRACT_URL = "https://api.elsevier.com/content/abstract/scopus_id"

    def __init__(self, api_key: str = "", inst_token: str = ""):
        self.api_key = api_key
        self.inst_token = inst_token
        self.enabled = bool(api_key and api_key.strip())
        self.headers: Dict[str, str] = {}
        if self.enabled:
            self.headers["X-ELS-APIKey"] = api_key
            self.headers["Accept"] = "application/json"
            if inst_token:
                self.headers["X-ELS-Insttoken"] = inst_token

    async def search_publications(
        self, author_name: str, affiliation: str = "Vignan", count: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search Scopus for publications by author name + affiliation.
        Returns a list of Scopus search result entries.
        """
        if not self.enabled:
            return []

        query = f'AUTHLASTNAME({author_name.split()[-1]})'
        if len(author_name.split()) > 1:
            first = author_name.split()[0]
            query = f'AUTHLASTNAME({author_name.split()[-1]}) AND AUTHFIRST({first})'
        if affiliation:
            query += f' AND AFFIL({affiliation})'

        params = {
            "query": query,
            "count": min(count, 25),
            "start": 0,
            "sort": "-coverDate",
        }

        results: List[Dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=20.0, headers=self.headers) as client:
            for page in range(2):  # Max 2 pages = 50 results
                params["start"] = page * 25
                for attempt in range(3):
                    try:
                        response = await client.get(self.SEARCH_URL, params=params)
                        if response.status_code in (401, 403):
                            logger.warning("Scopus API key invalid, unauthorized, or expired — disabling Scopus client")
                            self.enabled = False
                            return results
                        if response.status_code == 429:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        response.raise_for_status()
                        data = response.json()
                        search_results = data.get("search-results", {})
                        entries = search_results.get("entry", [])
                        if not entries or (len(entries) == 1 and entries[0].get("@_fa") == "true" and "error" in entries[0]):
                            return results
                        results.extend(entries)
                        total = int(search_results.get("opensearch:totalResults", 0))
                        if len(results) >= total:
                            return results
                        break
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code in (401, 403):
                            self.enabled = False
                        logger.error(f"Scopus HTTP error: {e}")
                        break
                    except Exception as e:
                        logger.error(f"Scopus search error: {e}")
                        await asyncio.sleep(1)
        return results

    async def search_author_works(
        self, author_id: str, count: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search Scopus publications directly by Scopus Author ID (AU-ID).
        Example: 54788460700 for Dr. M. Umadevi
        """
        if not self.enabled or not author_id:
            return []

        clean_id = str(author_id).replace("AUTHOR_ID:", "").strip()
        query = f"AU-ID({clean_id})"
        params = {
            "query": query,
            "count": min(count, 25),
            "start": 0,
            "sort": "-coverDate",
        }

        results: List[Dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=20.0, headers=self.headers) as client:
            for page in range(2):
                params["start"] = page * 25
                for attempt in range(3):
                    try:
                        response = await client.get(self.SEARCH_URL, params=params)
                        if response.status_code in (401, 403):
                            self.enabled = False
                            return results
                        if response.status_code == 429:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        response.raise_for_status()
                        data = response.json()
                        search_results = data.get("search-results", {})
                        entries = search_results.get("entry", [])
                        if not entries or (len(entries) == 1 and entries[0].get("@_fa") == "true" and "error" in entries[0]):
                            return results
                        results.extend(entries)
                        total = int(search_results.get("opensearch:totalResults", 0))
                        if len(results) >= total:
                            return results
                        break
                    except Exception as e:
                        logger.error(f"Scopus author works error: {e}")
                        await asyncio.sleep(1)

        return results

    async def search_author(self, name: str, affiliation: str = "Vignan") -> List[Dict[str, Any]]:
        """
        Search for Scopus Author IDs by name + affiliation.
        """
        if not self.enabled:
            return []

        query = f'AUTHLASTNAME({name.split()[-1]})'
        if len(name.split()) > 1:
            query += f' AND AUTHFIRST({name.split()[0]})'
        if affiliation:
            query += f' AND AFFIL({affiliation})'

        params = {"query": query, "count": 10}

        async with httpx.AsyncClient(timeout=15.0, headers=self.headers) as client:
            for attempt in range(3):
                try:
                    response = await client.get(self.AUTHOR_SEARCH_URL, params=params)
                    if response.status_code in (401, 403):
                        logger.warning("Scopus author search: auth error — disabling Scopus client")
                        self.enabled = False
                        return []
                    if response.status_code == 429:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    response.raise_for_status()
                    data = response.json()
                    entries = data.get("search-results", {}).get("entry", [])
                    if entries and not (len(entries) == 1 and "error" in entries[0]):
                        return entries
                    return []
                except Exception as e:
                    logger.error(f"Scopus author search error: {e}")
                    await asyncio.sleep(1)

        return []

    def extract_publication_data(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Extract normalized publication data from a Scopus search result entry."""
        return {
            "scopus_id": entry.get("dc:identifier", "").replace("SCOPUS_ID:", ""),
            "eid": entry.get("eid"),
            "doi": entry.get("prism:doi"),
            "title": entry.get("dc:title"),
            "journal_name": entry.get("prism:publicationName"),
            "issn": entry.get("prism:issn"),
            "eissn": entry.get("prism:eIssn"),
            "volume": entry.get("prism:volume"),
            "issue": entry.get("prism:issueIdentifier"),
            "pages": entry.get("prism:pageRange"),
            "cover_date": entry.get("prism:coverDate"),
            "publication_type": entry.get("subtypeDescription"),
            "cited_by_count": int(entry.get("citedby-count", 0)),
            "authors_raw": entry.get("dc:creator"),
            "affiliation": entry.get("affiliation", []),
            "source_id": entry.get("source-id"),
        }

    def extract_author_data(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Extract author identification data from a Scopus author search result."""
        return {
            "scopus_author_id": entry.get("dc:identifier", "").replace("AUTHOR_ID:", ""),
            "eid": entry.get("eid"),
            "name": entry.get("preferred-name", {}).get("surname", "")
                    + ", " + entry.get("preferred-name", {}).get("given-name", ""),
            "affiliation": entry.get("affiliation-current", {}).get("affiliation-name", ""),
            "document_count": int(entry.get("document-count", 0)),
            "cited_by_count": int(entry.get("cited-by-count", 0)),
            "h_index": entry.get("h-index"),
        }
