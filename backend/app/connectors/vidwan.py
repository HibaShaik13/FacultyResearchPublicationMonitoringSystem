"""
Vidwan (INFLIBNET) Public Profile Connector.

Provides safe, public-profile ingestion for faculty with verified Vidwan profile identifiers.
Extracts public publication records and metadata without requiring authenticated/private API keys.
"""

import asyncio
import html
import logging
import re
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)


class VidwanClient:
    """Client for querying public Vidwan / IRINS researcher profiles."""

    BASE_URL = "https://vidwan.inflibnet.ac.in"

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36 (Institutional Research Monitor)"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    async def get_profile_publications(self, vidwan_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves public publication list for a given Vidwan ID.
        Returns normalized publication dictionaries with provenance URLs.
        """
        clean_id = str(vidwan_id).strip()
        if not clean_id or not clean_id.isdigit():
            logger.warning(f"Invalid Vidwan ID format: '{vidwan_id}'")
            return []

        profile_url = f"{self.BASE_URL}/profile/{clean_id}"
        publications: List[Dict[str, Any]] = []

        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers, follow_redirects=True) as client:
                for attempt in range(2):
                    try:
                        response = await client.get(profile_url)
                        if response.status_code == 200:
                            publications = self._parse_profile_html(response.text, clean_id, profile_url)
                            logger.info(f"Vidwan: Found {len(publications)} publications for profile {clean_id}")
                            break
                        elif response.status_code == 404:
                            logger.info(f"Vidwan profile {clean_id} not found (HTTP 404)")
                            break
                        else:
                            logger.warning(f"Vidwan HTTP status {response.status_code} for profile {clean_id}")
                    except httpx.TimeoutException:
                        if attempt == 0:
                            await asyncio.sleep(1)
                        else:
                            logger.warning(f"Vidwan profile fetch timed out for {clean_id}")
                    except Exception as e:
                        logger.warning(f"Vidwan connection error for {clean_id}: {e}")
                        break
        except Exception as e:
            logger.error(f"Unexpected error querying Vidwan for profile {clean_id}: {e}")

        return publications

    def _parse_profile_html(self, html_text: str, vidwan_id: str, profile_url: str) -> List[Dict[str, Any]]:
        """
        Parses public HTML for publication entries.
        Supports standard Vidwan / IRINS publication listing layouts.
        """
        records: List[Dict[str, Any]] = []
        if not html_text:
            return records

        # Look for publication cards/blocks in standard Vidwan layout
        # Match list items or table rows containing publication details
        pub_blocks = re.findall(
            r'<div[^>]*class=["\'][^"\']*publication[^"\']*["\'][^>]*>(.*?)</div>',
            html_text,
            re.IGNORECASE | re.DOTALL,
        )

        if not pub_blocks:
            # Fallback: look for research output / article list patterns
            pub_blocks = re.findall(
                r'<li[^>]*class=["\'][^"\']*publication-item[^"\']*["\'][^>]*>(.*?)</li>',
                html_text,
                re.IGNORECASE | re.DOTALL,
            )

        # Fallback: look for general article titles inside table or cards
        if not pub_blocks:
            pub_blocks = re.findall(
                r'<div[^>]*class=["\'][^"\']*card-body[^"\']*["\'][^>]*>(.*?)</div>',
                html_text,
                re.IGNORECASE | re.DOTALL,
            )

        for idx, block in enumerate(pub_blocks):
            clean_block = re.sub(r'<[^>]+>', ' ', block)
            clean_block = html.unescape(clean_block)
            clean_block = re.sub(r'\s+', ' ', clean_block).strip()

            if len(clean_block) < 15:
                continue

            # Extract DOI if present
            doi_match = re.search(r'(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)', clean_block)
            doi = doi_match.group(1).rstrip('.') if doi_match else None

            # Extract Year if present
            year_match = re.search(r'\b(19\d{2}|20\d{2})\b', clean_block)
            year = int(year_match.group(1)) if year_match else None

            # Determine Title (first major sentence or before year/venue)
            title = clean_block
            if doi and doi in title:
                title = title.replace(doi, "").strip()

            if len(title) > 255:
                title = title[:252] + "..."

            if title:
                records.append({
                    "title": title,
                    "doi": doi,
                    "year": year,
                    "vidwan_id": vidwan_id,
                    "source_id": f"vidwan:{vidwan_id}:{idx + 1}" if not doi else doi,
                    "profile_url": profile_url,
                    "raw_text": clean_block[:500],
                })

        return records
