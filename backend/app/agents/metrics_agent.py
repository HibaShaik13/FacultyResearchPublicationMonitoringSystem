import logging
import uuid
from typing import Dict, Any, List
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.publication import Publication, PublicationAuthor
from app.models.faculty import FacultyProfile
from app.models.metrics import CitationSnapshot, FacultyMetricSnapshot
from app.models.provenance import ProvenanceRecord

logger = logging.getLogger(__name__)

class MetricsAgent:
    """Agent 9 - Citation & Research Metrics Agent"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.today = date.today()

    async def run(self) -> Dict[str, Any]:
        logger.info("Starting Research Metrics Agent (Phase 9 - Agent 9)")
        
        # Load publications with their sources
        stmt = select(Publication).options(
            selectinload(Publication.sources)
        )
        result = await self.session.execute(stmt)
        publications = result.scalars().unique().all()
        
        stats = {
            "pub_processed": 0,
            "pub_snapshots": 0,
            "faculty_processed": 0,
            "faculty_snapshots": 0,
            "calculated_metrics": 0,
            "missing_metrics": 0,
            "errors": 0
        }
        
        # 1. Process Publication Metrics
        for pub in publications:
            stats["pub_processed"] += 1
            try:
                await self._process_publication_metrics(pub, stats)
            except Exception as e:
                logger.error(f"Error processing metrics for pub {pub.id}: {e}")
                stats["errors"] += 1
                
        # 2. Process Faculty Metrics
        faculty_stmt = select(FacultyProfile).options(
            selectinload(FacultyProfile.publication_links).selectinload(PublicationAuthor.publication)
        ).where(FacultyProfile.status == "active")
        
        faculty_res = await self.session.execute(faculty_stmt)
        faculty_profiles = faculty_res.scalars().unique().all()
        
        for profile in faculty_profiles:
            stats["faculty_processed"] += 1
            try:
                await self._process_faculty_metrics(profile, stats)
            except Exception as e:
                logger.error(f"Error processing metrics for faculty {profile.id}: {e}")
                stats["errors"] += 1
                
        await self.session.commit()
        return stats

    async def _process_publication_metrics(self, pub: Publication, stats: Dict[str, Any]):
        best_count = -1
        best_source = None
        
        for source in pub.sources:
            if not source.raw_metadata:
                continue
                
            count = None
            if source.source_system == "openalex":
                count = source.raw_metadata.get("cited_by_count")
            elif source.source_system == "crossref":
                count = source.raw_metadata.get("is-referenced-by-count")
                
            if count is not None:
                # Idempotency
                stmt = select(CitationSnapshot).where(
                    CitationSnapshot.publication_id == pub.id,
                    CitationSnapshot.source == source.source_system,
                    CitationSnapshot.snapshot_date == self.today
                )
                existing = await self.session.execute(stmt)
                if not existing.scalars().first():
                    snapshot = CitationSnapshot(
                        publication_id=pub.id,
                        citation_count=count,
                        source=source.source_system,
                        snapshot_date=self.today
                    )
                    self.session.add(snapshot)
                    stats["pub_snapshots"] += 1
                    
                if count > best_count:
                    best_count = count
                    best_source = source.source_system
                    
        # Update publication latest count if found
        if best_count >= 0:
            if pub.citation_count != best_count or pub.citation_source != best_source:
                pub.citation_count = best_count
                pub.citation_source = best_source
        else:
            stats["missing_metrics"] += 1

    async def _process_faculty_metrics(self, profile: FacultyProfile, stats: Dict[str, Any]):
        # Idempotency
        stmt = select(FacultyMetricSnapshot).where(
            FacultyMetricSnapshot.faculty_id == profile.id,
            FacultyMetricSnapshot.snapshot_date == self.today
        )
        existing = await self.session.execute(stmt)
        if existing.scalars().first():
            return
            
        # Collect citations from attributed publications
        citations = []
        for link in profile.publication_links:
            pub = link.publication
            # use the canonical citation count computed earlier
            citations.append(pub.citation_count or 0)
            
        total_pubs = len(citations)
        total_citations = sum(citations)
        
        # Calculate h-index and i10-index
        citations.sort(reverse=True)
        h_index = 0
        for i, c in enumerate(citations):
            if c >= i + 1:
                h_index = i + 1
            else:
                break
                
        i10_index = sum(1 for c in citations if c >= 10)
        
        snapshot_id = uuid.uuid4()
        snapshot = FacultyMetricSnapshot(
            id=snapshot_id,
            faculty_id=profile.id,
            h_index=h_index,
            i10_index=i10_index,
            total_citations=total_citations,
            total_publications=total_pubs,
            verified_publications=total_pubs,  # Assuming all linked are verified for now
            snapshot_date=self.today
        )
        self.session.add(snapshot)
        stats["faculty_snapshots"] += 1
        stats["calculated_metrics"] += 2  # h-index, i10-index
        
        # Add provenance to clearly mark these as calculated from local graph
        prov = ProvenanceRecord(
            entity_type="faculty_metric_snapshot",
            entity_id=snapshot_id,
            event_type="metrics_calculated",
            source="system",
            detail=f"Calculated h-index ({h_index}) and i10-index ({i10_index}) from {total_pubs} publications.",
            agent_name="MetricsAgent"
        )
        self.session.add(prov)
