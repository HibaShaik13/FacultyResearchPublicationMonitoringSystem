"""
IEEE Xplore API connector.

Uses the IEEE Xplore REST API to:
- Discover publications by IEEE Author ID or Author Name + Affiliation.
- Retrieve full publication metadata including DOI, citation count, venue, and abstract.

Gated behind IEEE_API_KEY when available. Gracefully handles unconfigured/unauthorized states.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)


class IEEEClient:
    """Client for official IEEE Xplore REST API."""

    BASE_URL = "https://ieeexploreapi.ieee.org/api/v1/search/articles"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key.strip() if api_key else ""
        self.enabled = bool(self.api_key)

    async def search_publications(
        self, author_name: str, affiliation: str = "", max_records: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search IEEE Xplore by author name and optional institutional affiliation.
        """
        if not self.enabled:
            return []

        params = {
            "apikey": self.api_key,
            "format": "json",
            "max_records": min(max_records, 50),
            "author_facet": author_name,
        }
        if affiliation:
            params["affiliation"] = affiliation

        return await self._execute_query(params)

    async def get_author_works(
        self, author_id: str, max_records: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search IEEE Xplore publications directly by IEEE Author ID.
        Example: 37085445363 for Dr. M. Umadevi
        """
        if not self.enabled or not author_id:
            return []

        clean_id = str(author_id).strip()
        params = {
            "apikey": self.api_key,
            "format": "json",
            "max_records": min(max_records, 50),
            "author_id": clean_id,
        }
        return await self._execute_query(params)

    async def _execute_query(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=20.0) as client:
            for attempt in range(3):
                try:
                    response = await client.get(self.BASE_URL, params=params)
                    if response.status_code in (401, 403):
                        logger.warning("IEEE Xplore API key invalid or unauthorized — disabling IEEE client")
                        self.enabled = False
                        return []
                    if response.status_code == 429:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    response.raise_for_status()
                    data = response.json()
                    articles = data.get("articles", [])
                    return articles
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in (401, 403):
                        self.enabled = False
                    logger.error(f"IEEE Xplore HTTP error: {e}")
                    break
                except Exception as e:
                    logger.error(f"IEEE Xplore search error: {e}")
                    await asyncio.sleep(1)
        return results

    def extract_article_data(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize an IEEE Xplore article payload into canonical publication metadata."""
        authors_list = []
        authors_raw = []
        for auth in (article.get("authors", {}).get("authors", []) or []):
            name = auth.get("full_name") or auth.get("preferred_name") or f"{auth.get('first_name', '')} {auth.get('last_name', '')}".strip()
            if name:
                authors_raw.append(name)
                authors_list.append({
                    "name": name,
                    "id": auth.get("id"),
                    "affiliation": auth.get("affiliation", ""),
                })

        return {
            "title": article.get("title"),
            "doi": article.get("doi"),
            "year": int(article.get("publication_year")) if article.get("publication_year") else None,
            "venue": article.get("publication_title"),
            "publisher": article.get("publisher") or "IEEE",
            "abstract": article.get("abstract"),
            "source_url": article.get("html_url") or article.get("pdf_url"),
            "source_publication_id": str(article.get("article_number") or ""),
            "authors_raw": ", ".join(authors_raw),
            "authors_parsed": authors_list,
            "citation_count": int(article.get("citing_paper_count", 0)),
            "publication_type": article.get("content_type"),
            "raw_metadata": article,
        }
