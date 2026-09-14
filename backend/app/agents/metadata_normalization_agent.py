import logging
import re
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.publication import Publication

logger = logging.getLogger(__name__)

class MetadataNormalizationAgent:
    """Agent 4 - Metadata Normalization"""
    
    def __init__(self, session: AsyncSession):
        self.session = session

    async def run(self) -> Dict[str, Any]:
        logger.info("Starting Metadata Normalization (Phase 5 - Agent 4)")
        
        stmt = select(Publication).options(
            selectinload(Publication.sources)
        )
        result = await self.session.execute(stmt)
        publications = result.scalars().unique().all()
        
        stats = {
            "processed": 0,
            "normalized": 0,
            "errors": 0
        }
        
        for pub in publications:
            stats["processed"] += 1
            try:
                self._normalize_publication(pub)
                stats["normalized"] += 1
            except Exception as e:
                logger.error(f"Error normalizing publication {pub.id}: {e}")
                stats["errors"] += 1
                
        await self.session.commit()
        return stats

    def _normalize_publication(self, pub: Publication):
        # Prefer Crossref metadata if available, otherwise OpenAlex
        sources = pub.sources
        cr_source = next((s for s in sources if s.source_system == "crossref"), None)
        oa_source = next((s for s in sources if s.source_system == "openalex"), None)
        
        raw_metadata = {}
        if cr_source and cr_source.raw_metadata:
            raw_metadata = cr_source.raw_metadata
            self._apply_crossref_normalization(pub, raw_metadata)
        elif oa_source and oa_source.raw_metadata:
            raw_metadata = oa_source.raw_metadata
            self._apply_openalex_normalization(pub, raw_metadata)
            
        # Common normalization
        if pub.doi:
            # Strip https://doi.org/ and lowercase
            pub.doi = pub.doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip().lower()
            
        if pub.title:
            # Strip multiple spaces and lowercase for normalized title
            pub.normalized_title = re.sub(r'\s+', ' ', pub.title).strip().lower()
            
    def _apply_crossref_normalization(self, pub: Publication, metadata: Dict[str, Any]):
        # Authors
        authors = metadata.get("author", [])
        parsed_authors = []
        for i, auth in enumerate(authors):
            name = f"{auth.get('given', '')} {auth.get('family', '')}".strip()
            affils = [a.get('name') for a in auth.get('affiliation', [])]
            parsed_authors.append({
                "name": name,
                "position": i + 1,
                "affiliations": affils
            })
        if parsed_authors and not pub.authors_parsed:
            pub.authors_parsed = parsed_authors
            
        # Venue
        container = metadata.get("container-title", [])
        if container and not pub.journal_name:
            pub.journal_name = container[0]
            
        # Type
        type_str = metadata.get("type", "")
        if type_str and not pub.publication_type:
            if type_str == "journal-article":
                pub.publication_type = "journal-article"
            elif type_str == "proceedings-article":
                pub.publication_type = "conference-paper"
            else:
                pub.publication_type = "other"

    def _apply_openalex_normalization(self, pub: Publication, metadata: Dict[str, Any]):
        # Authors
        authorships = metadata.get("authorships", [])
        parsed_authors = []
        for i, auth in enumerate(authorships):
            author_data = auth.get("author", {})
            name = author_data.get("display_name", "").strip()
            affils = [inst.get("display_name") for inst in auth.get("institutions", [])]
            parsed_authors.append({
                "name": name,
                "position": i + 1,
                "affiliations": affils
            })
        if parsed_authors and not pub.authors_parsed:
            pub.authors_parsed = parsed_authors
            
        # Venue
        host_venue = metadata.get("primary_location", {})
        if host_venue:
            source = host_venue.get("source", {}) or {}
            venue_name = source.get("display_name")
            if venue_name and not pub.journal_name:
                pub.journal_name = venue_name
                
        # Type
        type_str = metadata.get("type", "")
        if type_str and not pub.publication_type:
            if type_str == "article":
                pub.publication_type = "journal-article"
            else:
                pub.publication_type = "other"
