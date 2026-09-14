import logging
import uuid
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from rapidfuzz import fuzz

from app.models.faculty import FacultyProfile
from app.models.publication import Publication, PublicationSource
from app.models.provenance import ProvenanceRecord
from app.models.affiliation import AffiliationVariant
from app.connectors.openalex import OpenAlexClient
from app.connectors.crossref import CrossrefClient
from app.connectors.scopus import ScopusClient
from app.connectors.semantic_scholar import SemanticScholarClient
from app.connectors.orcid import OrcidClient
from app.config import get_settings

logger = logging.getLogger(__name__)


async def _load_affiliation_variants(session: AsyncSession) -> List[str]:
    """Load affiliation variants from database, falling back to defaults."""
    try:
        result = await session.execute(select(AffiliationVariant.variant_text))
        db_variants = [row[0] for row in result.all()]
        if db_variants:
            return db_variants
    except Exception as e:
        logger.warning(f"Could not load affiliation variants from DB: {e}")

    # Fallback defaults if table is empty or unavailable
    return [
        "Vignan's Foundation for Science, Technology & Research",
        "VFSTR",
        "Vignan University",
        "Vignan's University",
        "Vignans Foundation",
        "Vignan Engineering College",
        "Vignan's Engineering College",
        "Vignan Institute of Technology and Science",
        "Vignan, Guntur",
        "Vignan, Vadlamudi",
    ]


class PublicationDiscoveryAgent:
    """Agent 3 - Publication Discovery (Multi-Source)"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        settings = get_settings()
        # Core connectors (always active)
        self.openalex = OpenAlexClient(email=settings.openalex_email or "research-admin@vignan.ac.in")
        self.crossref = CrossrefClient(email=settings.crossref_email or "research-admin@vignan.ac.in")
        # Optional connectors (gated behind API keys)
        self.scopus = ScopusClient(api_key=settings.scopus_api_key, inst_token=settings.scopus_inst_token)
        self.semantic_scholar = SemanticScholarClient(api_key=settings.semantic_scholar_api_key)
        self.orcid = OrcidClient(client_id=settings.orcid_client_id, client_secret=settings.orcid_client_secret)
        self.affiliation_variants: List[str] = []

    async def run(self) -> Dict[str, Any]:
        """Runs the publication discovery process for all active faculty."""
        logger.info("Starting Publication Discovery (Phase 4 — Multi-Source)")
        
        # Load affiliation variants from DB
        self.affiliation_variants = await _load_affiliation_variants(self.session)
        
        stmt = select(FacultyProfile).options(
            selectinload(FacultyProfile.name_variants),
            selectinload(FacultyProfile.identifiers)
        ).where(FacultyProfile.status == "active")
        
        result = await self.session.execute(stmt)
        profiles = result.scalars().all()
        
        stats = {
            "processed": 0,
            "publications_discovered": 0,
            "dois_found": 0,
            "duplicates_prevented": 0,
            "errors": 0,
            "sources_queried": {
                "openalex": 0,
                "crossref": 0,
                "scopus": 0,
                "semantic_scholar": 0,
                "orcid": 0,
            },
        }
        
        for profile in profiles:
            stats["processed"] += 1
            logger.info(f"Discovering publications for {profile.normalized_name}")
            
            # --- 1. OpenAlex ---
            try:
                verified_openalex = next((i for i in profile.identifiers if i.identifier_type == "openalex" and i.verified), None)
                oa_works = []
                if verified_openalex:
                    oa_works = await self.openalex.get_author_works(verified_openalex.identifier_value)
                else:
                    oa_works = await self.openalex.search_works_by_name(profile.normalized_name)
                    
                for work in oa_works:
                    if not verified_openalex and not self._is_vignan_work_openalex(work):
                        continue
                    await self._process_openalex_work(profile, work, stats)
                stats["sources_queried"]["openalex"] += 1
            except Exception as e:
                logger.error(f"Error in OpenAlex discovery for {profile.normalized_name}: {e}")
                stats["errors"] += 1

            # --- 2. Crossref ---
            try:
                cr_works = await self.crossref.search_works_by_author(profile.normalized_name, "Vignan")
                for work in cr_works:
                    await self._process_crossref_work(profile, work, stats)
                stats["sources_queried"]["crossref"] += 1
            except Exception as e:
                logger.error(f"Error in Crossref discovery for {profile.normalized_name}: {e}")
                stats["errors"] += 1

            # --- 3. Scopus (if API key configured) ---
            if self.scopus.enabled:
                try:
                    scopus_entries = await self.scopus.search_publications(profile.normalized_name, "Vignan")
                    for entry in scopus_entries:
                        await self._process_scopus_work(profile, entry, stats)
                    stats["sources_queried"]["scopus"] += 1
                except Exception as e:
                    logger.error(f"Error in Scopus discovery for {profile.normalized_name}: {e}")
                    stats["errors"] += 1

            # --- 4. Semantic Scholar ---
            try:
                s2_papers = await self.semantic_scholar.search_papers(profile.normalized_name)
                for paper in s2_papers:
                    await self._process_s2_work(profile, paper, stats)
                stats["sources_queried"]["semantic_scholar"] += 1
            except Exception as e:
                logger.error(f"Error in Semantic Scholar discovery for {profile.normalized_name}: {e}")
                stats["errors"] += 1

            # --- 5. ORCID (if faculty has ORCID identifier) ---
            try:
                verified_orcid = next((i for i in profile.identifiers if i.identifier_type == "orcid" and i.verified), None)
                if verified_orcid:
                    orcid_works = await self.orcid.get_works(verified_orcid.identifier_value)
                    for work in orcid_works:
                        await self._process_orcid_work(profile, work, stats)
                    stats["sources_queried"]["orcid"] += 1
            except Exception as e:
                logger.error(f"Error in ORCID discovery for {profile.normalized_name}: {e}")
                stats["errors"] += 1
                
        await self.session.commit()
        return stats

    def _is_vignan_work_openalex(self, work: Dict[str, Any]) -> bool:
        """Helper to verify if a raw OpenAlex work belongs to Vignan (used for fallback searches)"""
        authorships = work.get("authorships", [])
        for authorship in authorships:
            for inst in authorship.get("institutions", []):
                inst_name = inst.get("display_name", "").lower()
                for vfstr in self.affiliation_variants:
                    if fuzz.partial_ratio(vfstr.lower(), inst_name) > 80:
                        return True
        return False

    async def _check_source_exists(self, source_system: str, source_id: str) -> bool:
        """Idempotency check: does this source already exist?"""
        stmt = select(PublicationSource).where(
            PublicationSource.source_system == source_system,
            PublicationSource.source_id == source_id
        )
        existing = await self.session.execute(stmt)
        return existing.scalars().first() is not None

    async def _create_publication(
        self, profile: FacultyProfile, title: str, doi: str | None,
        year: int | None, source_system: str, source_id: str,
        raw_metadata: dict, stats: Dict[str, Any]
    ):
        """Create a Publication + PublicationSource + ProvenanceRecord."""
        pub_id = uuid.uuid4()
        pub = Publication(
            id=pub_id,
            title=title,
            normalized_title=title.lower().strip()[:255],
            doi=doi,
            year=year,
            publication_type="other",
            verification_status="pending"
        )
        self.session.add(pub)
        
        src = PublicationSource(
            publication_id=pub_id,
            source_system=source_system,
            source_id=source_id,
            raw_metadata=raw_metadata,
            discovery_method=f"{source_system}_api"
        )
        self.session.add(src)
        
        prov = ProvenanceRecord(
            entity_type="publication",
            entity_id=pub_id,
            event_type="discovered",
            source=source_system,
            detail=f"Discovered via {source_system} search for {profile.normalized_name}",
            agent_name="PublicationDiscoveryAgent"
        )
        self.session.add(prov)
        
        stats["publications_discovered"] += 1
        if doi:
            stats["dois_found"] += 1

    async def _process_openalex_work(self, profile: FacultyProfile, work: Dict[str, Any], stats: Dict[str, Any]):
        source_id = work.get("id")
        if not source_id:
            return
        if await self._check_source_exists("openalex", source_id):
            stats["duplicates_prevented"] += 1
            return
        doi = work.get("doi")
        if doi:
            doi = doi.replace("https://doi.org/", "")
        title = work.get("title") or "Unknown Title"
        year = work.get("publication_year")
        await self._create_publication(profile, title, doi, year, "openalex", source_id, work, stats)

    async def _process_crossref_work(self, profile: FacultyProfile, work: Dict[str, Any], stats: Dict[str, Any]):
        doi = work.get("DOI")
        if not doi:
            return
        if await self._check_source_exists("crossref", doi):
            stats["duplicates_prevented"] += 1
            return
        titles = work.get("title", [])
        title = titles[0] if titles else "Unknown Title"
        year = None
        issued = work.get("issued", {})
        date_parts = issued.get("date-parts", [[]])
        if date_parts and date_parts[0]:
            year = date_parts[0][0]
        await self._create_publication(profile, title, doi, year, "crossref", doi, work, stats)

    async def _process_scopus_work(self, profile: FacultyProfile, entry: Dict[str, Any], stats: Dict[str, Any]):
        """Process a Scopus search result entry."""
        data = self.scopus.extract_publication_data(entry)
        source_id = data.get("eid") or data.get("scopus_id")
        if not source_id:
            return
        if await self._check_source_exists("scopus", source_id):
            stats["duplicates_prevented"] += 1
            return
        doi = data.get("doi")
        title = data.get("title") or "Unknown Title"
        year = None
        cover_date = data.get("cover_date")
        if cover_date:
            try:
                year = int(cover_date[:4])
            except (ValueError, TypeError):
                pass
        await self._create_publication(profile, title, doi, year, "scopus", source_id, entry, stats)

    async def _process_s2_work(self, profile: FacultyProfile, paper: Dict[str, Any], stats: Dict[str, Any]):
        """Process a Semantic Scholar paper result."""
        data = self.semantic_scholar.extract_paper_data(paper)
        source_id = data.get("s2_paper_id")
        if not source_id:
            return
        if await self._check_source_exists("semantic_scholar", source_id):
            stats["duplicates_prevented"] += 1
            return
        doi = data.get("doi")
        title = data.get("title") or "Unknown Title"
        year = data.get("year")
        await self._create_publication(profile, title, doi, year, "semantic_scholar", source_id, paper, stats)

    async def _process_orcid_work(self, profile: FacultyProfile, work_summary: Dict[str, Any], stats: Dict[str, Any]):
        """Process an ORCID work-summary."""
        data = self.orcid.extract_work_data(work_summary)
        put_code = data.get("orcid_put_code")
        source_id = f"orcid:{put_code}" if put_code else None
        if not source_id:
            return
        if await self._check_source_exists("orcid", source_id):
            stats["duplicates_prevented"] += 1
            return
        doi = data.get("doi")
        title = data.get("title") or "Unknown Title"
        year = data.get("year")
        await self._create_publication(profile, title, doi, year, "orcid", source_id, work_summary, stats)
