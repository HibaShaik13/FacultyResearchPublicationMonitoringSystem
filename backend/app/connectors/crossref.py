import httpx
import logging
import asyncio
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class CrossrefClient:
    """Client for Crossref API."""

    BASE_URL = "https://api.crossref.org"

    def __init__(self, email: str = ""):
        self.email = email
        self.headers = {}
        # Crossref requires mailto in User-Agent for polite pool
        if self.email:
            self.headers["User-Agent"] = f"mailto:{self.email}"
            
    async def _fetch_works_paginated(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        url = f"{self.BASE_URL}/works"
        params["rows"] = 25
        results = []
        
        async with httpx.AsyncClient(timeout=20.0, headers=self.headers) as client:
            for page in range(0, 2):  # 2 pages, max 50 results
                params["offset"] = page * 25
                for attempt in range(3):
                    try:
                        response = await client.get(url, params=params)
                        response.raise_for_status()
                        data = response.json()
                        message = data.get("message", {})
                        items = message.get("items", [])
                        results.extend(items)
                        
                        if not items or len(results) >= message.get("total-results", 0):
                            return results
                        break
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 429:
                            await asyncio.sleep(2 ** attempt)
                        else:
                            logger.error(f"HTTP error querying Crossref: {e}")
                            break
                    except Exception as e:
                        logger.error(f"Error querying Crossref: {e}")
                        await asyncio.sleep(1)
                        
        return results

    async def search_works_by_author(self, name: str, affiliation: str = "") -> List[Dict[str, Any]]:
        """
        Fetch works by searching author name and affiliation.
        """
        # Crossref supports query.author and query.affiliation
        params = {
            "query.author": name,
        }
        if affiliation:
            params["query.affiliation"] = affiliation
            
        return await self._fetch_works_paginated(params)
