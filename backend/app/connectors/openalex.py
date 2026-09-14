import httpx
import logging
import asyncio
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class OpenAlexClient:
    """Client for OpenAlex API."""

    BASE_URL = "https://api.openalex.org"

    def __init__(self, email: str = ""):
        self.email = email
        self.headers = {}
        # OpenAlex uses the polite pool if an email is provided
        if self.email:
            self.headers["User-Agent"] = f"mailto:{self.email}"
            
    async def search_authors(self, name: str) -> List[Dict[str, Any]]:
        """
        Searches for authors by name.
        OpenAlex allows search in display_name.
        Returns a list of candidate author objects.
        """
        url = f"{self.BASE_URL}/authors"
        params = {
            "search": name,
            "per_page": 20,
        }
        
        async with httpx.AsyncClient(timeout=15.0, headers=self.headers) as client:
            # Basic retry logic for transient errors
            for attempt in range(3):
                try:
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    data = response.json()
                    return data.get("results", [])
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        await asyncio.sleep(2 ** attempt)
                    else:
                        logger.error(f"HTTP error querying OpenAlex for author '{name}': {e}")
                        break
                except Exception as e:
                    logger.error(f"Error querying OpenAlex for author '{name}': {e}")
                    await asyncio.sleep(1)
            return []

    async def _fetch_works_paginated(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Helper to fetch works with pagination, limited to first 2 pages (50 max) for safety."""
        url = f"{self.BASE_URL}/works"
        params["per_page"] = 25
        results = []
        
        async with httpx.AsyncClient(timeout=20.0, headers=self.headers) as client:
            for page in range(1, 3):  # Limit to 2 pages (50 results) to prevent unbounded crawling
                params["page"] = page
                for attempt in range(3):
                    try:
                        response = await client.get(url, params=params)
                        response.raise_for_status()
                        data = response.json()
                        page_results = data.get("results", [])
                        results.extend(page_results)
                        
                        # Break early if no more pages
                        meta = data.get("meta", {})
                        if not page_results or len(results) >= meta.get("count", 0):
                            return results
                        break
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 429:
                            await asyncio.sleep(2 ** attempt)
                        else:
                            logger.error(f"HTTP error querying OpenAlex works: {e}")
                            break
                    except Exception as e:
                        logger.error(f"Error querying OpenAlex works: {e}")
                        await asyncio.sleep(1)
                        
        return results

    async def get_author_works(self, openalex_id: str) -> List[Dict[str, Any]]:
        """Fetch works by a specific OpenAlex Author ID."""
        # e.g., openalex_id could be 'https://openalex.org/A123' or just 'A123'
        author_id_short = openalex_id.split("/")[-1]
        params = {"filter": f"author.id:{author_id_short}"}
        return await self._fetch_works_paginated(params)

    async def search_works_by_name(self, name: str) -> List[Dict[str, Any]]:
        """
        Fetch works by searching author name.
        Note: author.display_name.search is for Authors API.
        For Works API, we use default.search.
        """
        params = {
            "filter": f"default.search:{name}"
        }
        return await self._fetch_works_paginated(params)
