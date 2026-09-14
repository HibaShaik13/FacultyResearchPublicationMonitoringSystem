"""
Google Scholar connector via SerpAPI.

Uses the SerpAPI Google Scholar Profiles + Google Scholar Author endpoints
to search faculty profiles and retrieve citation metrics.

Requires a GOOGLE_SCHOLAR_SERPAPI_KEY. If key is empty, all methods return empty results.
"""

import httpx
import logging
import asyncio
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class GoogleScholarClient:
    """Client for Google Scholar via SerpAPI."""

    BASE_URL = "https://serpapi.com/search"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.enabled = bool(api_key and api_key.strip())

    async def search_author_profile(
        self, name: str, affiliation: str = "Vignan"
    ) -> List[Dict[str, Any]]:
        """
        Search Google Scholar for author profiles matching name and affiliation.
        Returns list of author profiles with citations, h-index, and i10-index.
        """
        if not self.enabled:
            return []

        params = {
            "engine": "google_scholar_profiles",
            "mauthors": f"{name} {affiliation}",
            "api_key": self.api_key,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            for attempt in range(3):
                try:
                    response = await client.get(self.BASE_URL, params=params)
                    if response.status_code == 429:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    response.raise_for_status()
                    data = response.json()
                    return data.get("profiles", [])
                except httpx.HTTPStatusError as e:
                    logger.error(f"Google Scholar profile search HTTP error: {e}")
                    break
                except Exception as e:
                    logger.error(f"Google Scholar profile search error: {e}")
                    await asyncio.sleep(1)

        return []

    async def get_author_articles(
        self, author_id: str, num: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get articles for a Google Scholar author ID.
        """
        if not self.enabled:
            return []

        params = {
            "engine": "google_scholar_author",
            "author_id": author_id,
            "num": num,
            "sort": "pubdate",
            "api_key": self.api_key,
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            for attempt in range(3):
                try:
                    response = await client.get(self.BASE_URL, params=params)
                    if response.status_code == 429:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    response.raise_for_status()
                    data = response.json()
                    return data.get("articles", [])
                except Exception as e:
                    logger.error(f"Google Scholar articles error: {e}")
                    await asyncio.sleep(1)

        return []

    def extract_profile_data(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Extract identity info from a Google Scholar profile."""
        cited_by = profile.get("cited_by", 0)
        return {
            "scholar_id": profile.get("author_id", ""),
            "name": profile.get("name", ""),
            "affiliations": profile.get("affiliations", ""),
            "email_domain": profile.get("email", ""),
            "cited_by": cited_by,
            "interests": [i.get("title", "") for i in profile.get("interests", [])],
            "thumbnail": profile.get("thumbnail", ""),
        }
