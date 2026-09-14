"""
ORCID Public API v3.0 connector.

Uses the public ORCID API (no authentication required for reads):
- Search: find ORCID profiles by faculty name + affiliation keywords.
- Works: fetch publication list for a known ORCID iD.
"""

import httpx
import logging
import asyncio
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class OrcidClient:
    """Client for ORCID Public API v3.0."""

    BASE_URL = "https://pub.orcid.org/v3.0"

    def __init__(self, client_id: str = "", client_secret: str = ""):
        self.client_id = client_id
        self.client_secret = client_secret
        self.headers = {
            "Accept": "application/json",
        }
        # Public API reads don't require auth tokens, but having credentials
        # can help with rate limits.

    async def search_by_name(
        self, name: str, affiliation: str = "Vignan", max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search ORCID for profiles matching a name and affiliation.
        Returns list of ORCID result records with orcid-identifier info.
        """
        # Build Lucene query for ORCID expanded-search
        parts = name.strip().split()
        if len(parts) >= 2:
            query = f'family-name:{parts[-1]} AND given-names:{parts[0]}'
        else:
            query = f'family-name:{name}'

        if affiliation:
            query += f' AND affiliation-org-name:{affiliation}'

        url = f"{self.BASE_URL}/expanded-search/"
        params = {"q": query, "rows": max_results, "start": 0}

        async with httpx.AsyncClient(timeout=15.0, headers=self.headers) as client:
            for attempt in range(3):
                try:
                    response = await client.get(url, params=params)
                    if response.status_code == 429:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    response.raise_for_status()
                    data = response.json()
                    results = data.get("expanded-result", [])
                    return results if results else []
                except httpx.HTTPStatusError as e:
                    logger.error(f"ORCID search HTTP error: {e}")
                    break
                except Exception as e:
                    logger.error(f"ORCID search error: {e}")
                    await asyncio.sleep(1)

        return []

    async def get_works(self, orcid_id: str) -> List[Dict[str, Any]]:
        """
        Fetch all works/publications for a given ORCID iD.
        Returns list of work-summary dicts.
        """
        url = f"{self.BASE_URL}/{orcid_id}/works"

        async with httpx.AsyncClient(timeout=20.0, headers=self.headers) as client:
            for attempt in range(3):
                try:
                    response = await client.get(url)
                    if response.status_code == 429:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    if response.status_code == 404:
                        logger.warning(f"ORCID profile not found: {orcid_id}")
                        return []
                    response.raise_for_status()
                    data = response.json()

                    works = []
                    groups = data.get("group", [])
                    for group in groups:
                        summaries = group.get("work-summary", [])
                        if summaries:
                            works.append(summaries[0])  # Take first summary per group
                    return works

                except httpx.HTTPStatusError as e:
                    logger.error(f"ORCID works HTTP error for {orcid_id}: {e}")
                    break
                except Exception as e:
                    logger.error(f"ORCID works error for {orcid_id}: {e}")
                    await asyncio.sleep(1)

        return []

    def extract_work_data(self, work_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Extract normalized publication data from an ORCID work-summary."""
        title_obj = work_summary.get("title", {})
        title_val = title_obj.get("title", {}).get("value", "") if title_obj else ""

        # Extract DOI from external-ids
        doi = None
        ext_ids = work_summary.get("external-ids", {})
        for eid in (ext_ids.get("external-id", []) if ext_ids else []):
            if eid.get("external-id-type") == "doi":
                doi = eid.get("external-id-value")
                break

        # Year
        year = None
        pub_date = work_summary.get("publication-date")
        if pub_date and pub_date.get("year"):
            try:
                year = int(pub_date["year"]["value"])
            except (ValueError, TypeError):
                pass

        journal = None
        journal_title = work_summary.get("journal-title")
        if journal_title:
            journal = journal_title.get("value")

        work_type = work_summary.get("type", "other")

        return {
            "title": title_val,
            "doi": doi,
            "year": year,
            "journal_name": journal,
            "publication_type": work_type,
            "orcid_put_code": work_summary.get("put-code"),
            "source_name": work_summary.get("source", {}).get("source-name", {}).get("value"),
        }

    def extract_profile_data(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract identity info from an ORCID expanded-search result."""
        return {
            "orcid_id": result.get("orcid-id", ""),
            "given_names": result.get("given-names", ""),
            "family_name": result.get("family-names", ""),
            "institution_names": result.get("institution-name", []),
            "email": result.get("email", []),
        }
