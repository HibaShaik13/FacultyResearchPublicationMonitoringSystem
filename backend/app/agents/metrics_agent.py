import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.faculty import FacultyProfile
from app.models.metrics import CitationSnapshot, FacultyMetricSnapshot
from app.models.provenance import ProvenanceRecord
from app.connectors.openalex import OpenAlexClient
from app.connectors.crossref import CrossrefClient
from app.connectors.semantic_scholar import SemanticScholarClient
from app.config import get_settings

logger = logging.getLogger(__name__)

# Source Priority order: Scopus -> OpenAlex -> Crossref -> Semantic Scholar
SOURCE_PRIORITY = {
    "scopus": 40,
    "openalex": 30,
    "crossref": 20,
    "semantic_scholar": 10,
    "csv_import": 0,
}

class MetricsAgent:
    """Agent 9 - Citation & Research Metrics Agent"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.today = date.today()
        settings = get_settings()
        self.openalex = OpenAlexClient(email=settings.openalex_email or "research-admin@vignan.ac.in")
        self.crossref = CrossrefClient(email=settings.crossref_email or "research-admin@vignan.ac.in")
        self.s2 = SemanticScholarClient(api_key=settings.semantic_scholar_api_key)

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
        with self.session.no_autoflush:
            for pub in publications:
                stats["pub_processed"] += 1
                try:
                    await self._process_publication_metrics(pub, stats)
                except Exception as e:
                    logger.error(f"Error processing metrics for pub {pub.id}: {e}")
                    stats["errors"] += 1

        await self.session.flush()

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

    async def _fetch_external_doi_citations(self, pub: Publication) -> Optional[int]:
        """Fetch live citation count from external APIs by DOI if not already in sources."""
        if not pub.doi:
            return None

        clean_doi = pub.doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip().lower()

        # 1. Try OpenAlex by DOI
        try:
            work = await self.openalex.get_work_by_doi(clean_doi)
            if work and "cited_by_count" in work:
                cnt = work["cited_by_count"]
                src = PublicationSource(
                    id=uuid.uuid4(),
                    publication_id=pub.id,
                    source_system="openalex",
                    source_id=work.get("id", f"doi:{clean_doi}"),
                    raw_metadata=work,
                    discovery_method="doi_lookup"
                )
                self.session.add(src)
                pub.sources.append(src)
                return cnt
        except Exception as e:
            logger.debug(f"OpenAlex DOI lookup failed for {clean_doi}: {e}")

        # 2. Try Crossref by DOI
        try:
            cr_meta = await self.crossref.get_work_by_doi(clean_doi)
            if cr_meta and "is-referenced-by-count" in cr_meta:
                cnt = cr_meta["is-referenced-by-count"]
                src = PublicationSource(
                    id=uuid.uuid4(),
                    publication_id=pub.id,
                    source_system="crossref",
                    source_id=clean_doi,
                    raw_metadata=cr_meta,
                    discovery_method="doi_lookup"
                )
                self.session.add(src)
                pub.sources.append(src)
                return cnt
        except Exception as e:
            logger.debug(f"Crossref DOI lookup failed for {clean_doi}: {e}")

        return None

    async def _process_publication_metrics(self, pub: Publication, stats: Dict[str, Any]):
        selected_count = -1
        selected_source = None
        highest_priority = -1

        for source in pub.sources:
            if not source.raw_metadata:
                continue
                
            count = None
            if source.source_system == "scopus":
                count = source.raw_metadata.get("citedby-count")
            elif source.source_system == "openalex":
                count = source.raw_metadata.get("cited_by_count")
            elif source.source_system == "crossref":
                count = source.raw_metadata.get("is-referenced-by-count")
            elif source.source_system == "semantic_scholar":
                count = source.raw_metadata.get("citationCount")
                
            if count is not None:
                try:
                    count = int(count)
                except (ValueError, TypeError):
                    continue

                # Record snapshot for historical audit
                stmt = select(CitationSnapshot).where(
                    CitationSnapshot.publication_id == pub.id,
                    CitationSnapshot.source == source.source_system,
                    CitationSnapshot.snapshot_date == self.today
                )
                existing = (await self.session.execute(stmt)).scalars().first()
                if not existing:
                    snapshot = CitationSnapshot(
                        publication_id=pub.id,
                        citation_count=count,
                        source=source.source_system,
                        snapshot_date=self.today
                    )
                    self.session.add(snapshot)
                    stats["pub_snapshots"] += 1

                # Select best citation count based on source priority and value
                prio = SOURCE_PRIORITY.get(source.source_system, 0)
                if prio > highest_priority or (prio == highest_priority and count > selected_count):
                    highest_priority = prio
                    selected_count = count
                    selected_source = source.source_system

        # If no citation metadata found from existing sources and DOI exists, try live DOI query
        if selected_count < 0 and pub.doi:
            ext_count = await self._fetch_external_doi_citations(pub)
            if ext_count is not None:
                selected_count = ext_count
                selected_source = "openalex" if "openalex" in [s.source_system for s in pub.sources] else "crossref"

        # Update publication canonical count
        if selected_count >= 0:
            if pub.citation_count != selected_count or pub.citation_source != selected_source:
                pub.citation_count = selected_count
                pub.citation_source = selected_source
        else:
            stats["missing_metrics"] += 1

    async def _process_faculty_metrics(self, profile: FacultyProfile, stats: Dict[str, Any]):
        # Collect citations from attributed publications
        citations = []
        for link in profile.publication_links:
            pub = link.publication
            if pub:
                citations.append(pub.citation_count or 0)
            
        total_pubs = len(citations)
        total_citations = sum(citations)
        
        # Calculate standard Hirsch h-index
        citations.sort(reverse=True)
        h_index = 0
        for i, c in enumerate(citations):
            if c >= i + 1:
                h_index = i + 1
            else:
                break
                
        # Calculate i10-index
        i10_index = sum(1 for c in citations if c >= 10)
        
        # Check if metric snapshot exists for today; upsert if found
        stmt = select(FacultyMetricSnapshot).where(
            FacultyMetricSnapshot.faculty_id == profile.id,
            FacultyMetricSnapshot.snapshot_date == self.today
        )
        existing = (await self.session.execute(stmt)).scalars().first()

        if existing:
            existing.h_index = h_index
            existing.i10_index = i10_index
            existing.total_citations = total_citations
            existing.total_publications = total_pubs
            existing.verified_publications = total_pubs
            snapshot_id = existing.id
        else:
            snapshot_id = uuid.uuid4()
            snapshot = FacultyMetricSnapshot(
                id=snapshot_id,
                faculty_id=profile.id,
                h_index=h_index,
                i10_index=i10_index,
                total_citations=total_citations,
                total_publications=total_pubs,
                verified_publications=total_pubs,
                snapshot_date=self.today
            )
            self.session.add(snapshot)
            stats["faculty_snapshots"] += 1

        stats["calculated_metrics"] += 2  # h-index, i10-index
        
        # Add provenance to track calculation
        prov = ProvenanceRecord(
            entity_type="faculty_metric_snapshot",
            entity_id=snapshot_id,
            event_type="metrics_calculated",
            source="system",
            detail=f"Calculated h-index ({h_index}) and i10-index ({i10_index}) from {total_pubs} publications.",
            agent_name="MetricsAgent"
        )
        self.session.add(prov)
