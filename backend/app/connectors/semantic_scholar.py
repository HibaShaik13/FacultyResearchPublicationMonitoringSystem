"""
Semantic Scholar Graph API v1 connector.

Uses:
- Paper Search: discover publications by query.
- Author Search: resolve faculty → S2 Author IDs.
- Paper details: citation counts and references.

API key is optional but recommended for higher rate limits.
"""

import httpx
import logging
import asyncio
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class SemanticScholarClient:
    """Client for Semantic Scholar Academic Graph API."""

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.headers: Dict[str, str] = {}
        if api_key and api_key.strip():
            self.headers["x-api-key"] = api_key

    async def search_papers(
        self, query: str, limit: int = 50, fields: str = "paperId,externalIds,title,year,citationCount,journal,authors,publicationTypes"
    ) -> List[Dict[str, Any]]:
        """
        Search papers by query string.
        """
        url = f"{self.BASE_URL}/paper/search"
        params = {"query": query, "limit": min(limit, 100), "fields": fields}

        results: List[Dict[str, Any]] = []
        max_attempts = 3 if self.api_key else 1
        async with httpx.AsyncClient(timeout=15.0, headers=self.headers) as client:
            for attempt in range(max_attempts):
                try:
                    response = await client.get(url, params=params)
                    if response.status_code == 429:
                        if not self.api_key:
                            logger.info(f"S2 public rate limit reached for '{query}'. Skipping unauthenticated S2 query.")
                            break
                        wait = int(response.headers.get("Retry-After", 2 ** attempt))
                        await asyncio.sleep(min(wait, 4))
                        continue
                    response.raise_for_status()
                    data = response.json()
                    return data.get("data", [])
                except httpx.HTTPStatusError as e:
                    logger.error(f"S2 paper search HTTP error: {e}")
                    break
                except Exception as e:
                    logger.error(f"S2 paper search error: {e}")
                    await asyncio.sleep(1)

        return results

    async def search_author(
        self, name: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for authors by name.
        """
        url = f"{self.BASE_URL}/author/search"
        params = {
            "query": name,
            "limit": limit,
            "fields": "authorId,name,affiliations,paperCount,citationCount,hIndex",
        }

        async with httpx.AsyncClient(timeout=15.0, headers=self.headers) as client:
            for attempt in range(3):
                try:
                    response = await client.get(url, params=params)
                    if response.status_code == 429:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    response.raise_for_status()
                    data = response.json()
                    return data.get("data", [])
                except Exception as e:
                    logger.error(f"S2 author search error: {e}")
                    await asyncio.sleep(1)

        return []

    async def get_author_papers(
        self, author_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fetch papers for a specific S2 Author ID.
        """
        url = f"{self.BASE_URL}/author/{author_id}/papers"
        params = {
            "limit": min(limit, 100),
            "fields": "paperId,externalIds,title,year,citationCount,journal,publicationTypes",
        }

        async with httpx.AsyncClient(timeout=20.0, headers=self.headers) as client:
            for attempt in range(3):
                try:
                    response = await client.get(url, params=params)
                    if response.status_code == 429:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    if response.status_code == 404:
                        return []
                    response.raise_for_status()
                    data = response.json()
                    return data.get("data", [])
                except Exception as e:
                    logger.error(f"S2 author papers error: {e}")
                    await asyncio.sleep(1)

        return []

    async def get_paper_by_doi(
        self, doi: str, fields: str = "paperId,externalIds,title,year,citationCount,journal,authors,publicationTypes"
    ) -> Dict[str, Any] | None:
        """Fetch a single paper by DOI from Semantic Scholar."""
        if not doi:
            return None
        clean_doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
        url = f"{self.BASE_URL}/paper/DOI:{clean_doi}"
        params = {"fields": fields}
        async with httpx.AsyncClient(timeout=15.0, headers=self.headers) as client:
            for attempt in range(3):
                try:
                    response = await client.get(url, params=params)
                    if response.status_code == 404:
                        return None
                    if response.status_code == 429:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    response.raise_for_status()
                    return response.json()
                except httpx.HTTPStatusError as e:
                    logger.warning(f"S2 get_paper_by_doi HTTP error for {clean_doi}: {e}")
                    break
                except Exception as e:
                    logger.warning(f"S2 get_paper_by_doi error for {clean_doi}: {e}")
                    await asyncio.sleep(1)
        return None

    def extract_paper_data(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """Extract normalized publication data from an S2 paper result."""
        ext_ids = paper.get("externalIds", {}) or {}
        journal = paper.get("journal", {}) or {}

        return {
            "s2_paper_id": paper.get("paperId"),
            "doi": ext_ids.get("DOI"),
            "arxiv_id": ext_ids.get("ArXiv"),
            "title": paper.get("title"),
            "year": paper.get("year"),
            "citation_count": paper.get("citationCount", 0),
            "journal_name": journal.get("name"),
            "journal_volume": journal.get("volume"),
            "journal_pages": journal.get("pages"),
            "publication_types": paper.get("publicationTypes", []),
        }
