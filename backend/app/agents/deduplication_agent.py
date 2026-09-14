import logging
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from rapidfuzz import fuzz

from app.models.publication import Publication, PublicationSource, PublicationAuthor
from app.models.review import ReviewTask

logger = logging.getLogger(__name__)

class DeduplicationAgent:
    """Agent 5 - Publication Deduplication & Entity Resolution"""
    
    def __init__(self, session: AsyncSession):
        self.session = session

    async def run(self) -> Dict[str, Any]:
        logger.info("Starting Publication Deduplication (Phase 5 - Agent 5)")
        
        # Load all publications that haven't been successfully merged and deleted
        stmt = select(Publication).options(
            selectinload(Publication.sources),
            selectinload(Publication.authors)
        )
        result = await self.session.execute(stmt)
        publications = result.scalars().unique().all()
        
        stats = {
            "processed": len(publications),
            "merged": 0,
            "ambiguous": 0,
            "errors": 0
        }
        
        # Group by DOI
        by_doi: Dict[str, List[Publication]] = {}
        no_doi: List[Publication] = []
        
        for pub in publications:
            if pub.doi:
                by_doi.setdefault(pub.doi, []).append(pub)
            else:
                no_doi.append(pub)
                
        # Track deleted IDs
        deleted_ids: set = set()

        # Handle Exact DOI matches
        for doi, pubs in by_doi.items():
            if len(pubs) > 1:
                try:
                    await self._merge_publications(pubs, stats, deleted_ids)
                except Exception as e:
                    logger.error(f"Error merging DOI {doi}: {e}")
                    stats["errors"] += 1

        # Handle Fuzzy matches for publications without DOI
        for i, p1 in enumerate(no_doi):
            if p1.id in deleted_ids:
                continue
            
            for p2 in publications:
                if p1.id == p2.id or p2.id in deleted_ids:
                    continue
                
                # Check year match
                if p1.year and p2.year and p1.year != p2.year:
                    continue
                    
                score = fuzz.ratio(p1.normalized_title, p2.normalized_title)
                
                if score > 95:
                    try:
                        await self._merge_publications([p1, p2], stats, deleted_ids)
                    except Exception as e:
                        logger.error(f"Error fuzzy merging {p1.id} and {p2.id}: {e}")
                        stats["errors"] += 1
                elif score > 85:
                    # Ambiguous - create review task
                    await self._create_duplicate_review_task(p1, p2, score, stats)

        await self.session.commit()
        return stats

    async def _merge_publications(self, pubs: List[Publication], stats: Dict[str, Any], deleted_ids: set = None):
        """Merges multiple publications into a single canonical record."""
        # Choose canonical: The one with the most sources, or oldest
        canonical = max(pubs, key=lambda p: (len(p.sources), p.created_at))
        
        for pub in pubs:
            if pub.id == canonical.id:
                continue
                
            # Reassign sources
            for source in list(pub.sources):
                # Ensure no duplicate source system + source id
                existing = any(
                    s.source_system == source.source_system and s.source_id == source.source_id
                    for s in canonical.sources
                )
                if not existing:
                    source.publication_id = canonical.id
                    canonical.sources.append(source)
                else:
                    self.session.delete(source) # Duplicate source on the same publication
                    
            # Reassign authors
            for author in list(pub.authors):
                author.publication_id = canonical.id
                canonical.authors.append(author)
                
            # Merge fields if missing in canonical
            if not canonical.journal_name and pub.journal_name:
                canonical.journal_name = pub.journal_name
            if not canonical.publication_type and pub.publication_type:
                canonical.publication_type = pub.publication_type
            if not canonical.authors_parsed and pub.authors_parsed:
                canonical.authors_parsed = pub.authors_parsed
                
            # Delete the duplicate
            self.session.delete(pub)
            if deleted_ids is not None:
                deleted_ids.add(pub.id)
            stats["merged"] += 1

    async def _create_duplicate_review_task(self, p1: Publication, p2: Publication, score: float, stats: Dict[str, Any]):
        """Create a ReviewTask for uncertain duplicates."""
        # Check idempotency
        stmt = select(ReviewTask).where(
            ReviewTask.task_type == "duplicate_uncertain",
            ReviewTask.entity_id == p1.id,
            ReviewTask.related_entity_id == p2.id
        )
        existing = await self.session.execute(stmt)
        if existing.scalars().first():
            return
            
        task = ReviewTask(
            task_type="duplicate_uncertain",
            priority="medium",
            entity_type="publication",
            entity_id=p1.id,
            related_entity_id=p2.id,
            explanation=f"Potential duplicate publications. Fuzzy title match score: {score:.2f}",
            evidence={
                "pub1_title": p1.title,
                "pub2_title": p2.title,
                "pub1_year": p1.year,
                "pub2_year": p2.year
            },
            agent_name="DeduplicationAgent"
        )
        self.session.add(task)
        stats["ambiguous"] += 1
