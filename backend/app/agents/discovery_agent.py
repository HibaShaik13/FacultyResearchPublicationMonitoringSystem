import logging
import re
import uuid
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from rapidfuzz import fuzz

from app.models.faculty import FacultyProfile, FacultyIdentifier
from app.models.publication import Publication, PublicationSource, PublicationAuthor
from app.models.provenance import ProvenanceRecord
from app.models.affiliation import AffiliationVariant
from app.connectors.openalex import OpenAlexClient
from app.connectors.crossref import CrossrefClient
from app.connectors.scopus import ScopusClient
from app.connectors.semantic_scholar import SemanticScholarClient
from app.connectors.orcid import OrcidClient
from app.connectors.ieee import IEEEClient
from app.connectors.vidwan import VidwanClient
from app.config import get_settings

logger = logging.getLogger(__name__)


async def _load_affiliation_variants(session: AsyncSession) -> List[str]:
    """Load affiliation variants from database, falling back to defaults for VFSTR."""
    try:
        result = await session.execute(select(AffiliationVariant.variant_text))
        db_variants = [row[0] for row in result.all()]
        if db_variants:
            return db_variants
    except Exception as e:
        logger.warning(f"Could not load affiliation variants from DB: {e}")

    # Fallback defaults for VFSTR (Vignan's Foundation for Science, Technology & Research, Vadlamudi)
    # Must NOT include sibling institutions (VLITS Lara, VITS Hyderabad, VIIT Vizag, Nirula)
    return [
        "Vignan's Foundation for Science, Technology & Research",
        "Vignan Foundation for Science, Technology and Research",
        "VFSTR",
        "VFSTR Deemed to be University",
        "Vignan's University",
        "Vignan University",
        "Vignans Foundation for Science Technology and Research",
        "Vignan's Engineering College, Vadlamudi",
        "Vignan, Vadlamudi",
        "Vignan, Guntur",
    ]


class PublicationDiscoveryAgent:
    """Agent 3 - Publication Discovery (Multi-Source: OpenAlex, Crossref, Scopus, IEEE Xplore, Semantic Scholar, ORCID, Vidwan)"""

    def __init__(self, session: AsyncSession):
        self.session = session
        settings = get_settings()
        # Core connectors (always active)
        self.openalex = OpenAlexClient(email=settings.openalex_email or "research-admin@vignan.ac.in")
        self.crossref = CrossrefClient(email=settings.crossref_email or "research-admin@vignan.ac.in")
        # Optional connectors (gated behind API keys / public profiles)
        self.scopus = ScopusClient(api_key=settings.scopus_api_key, inst_token=settings.scopus_inst_token)
        self.ieee = IEEEClient(api_key=settings.ieee_api_key)
        self.semantic_scholar = SemanticScholarClient(api_key=settings.semantic_scholar_api_key)
        self.orcid = OrcidClient(client_id=settings.orcid_client_id, client_secret=settings.orcid_client_secret)
        self.vidwan = VidwanClient()
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
                "ieee": 0,
                "semantic_scholar": 0,
                "orcid": 0,
            },
        }

        for profile in profiles:
            await self.discover_for_faculty(profile, stats)

        await self.session.commit()
        return stats

    async def discover_for_faculty(self, profile: FacultyProfile, stats: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Runs targeted publication discovery for a single faculty member across all active/verified connectors."""
        if stats is None:
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
                    "ieee": 0,
                    "semantic_scholar": 0,
                    "orcid": 0,
                    "vidwan": 0,
                },
            }
        stats["processed"] += 1
        logger.info(f"Discovering publications for {profile.normalized_name}")

        # Ensure affiliation variants loaded
        if not self.affiliation_variants:
            self.affiliation_variants = await _load_affiliation_variants(self.session)

        # Safely extract identifiers for this faculty profile
        identifiers = []
        try:
            raw_ids = getattr(profile, "identifiers", None)
            if raw_ids is not None:
                identifiers = list(raw_ids)
        except Exception:
            try:
                ident_res = await self.session.execute(
                    select(FacultyIdentifier).where(FacultyIdentifier.faculty_id == profile.id)
                )
                identifiers = list(ident_res.scalars().all())
            except Exception:
                identifiers = []

        if "sources_queried" not in stats:
            stats["sources_queried"] = {}

        # --- 1. OpenAlex ---
        try:
            verified_openalex = next((i for i in identifiers if i.identifier_type == "openalex" and i.verified), None)
            if verified_openalex:
                oa_works = await self.openalex.get_author_works(verified_openalex.identifier_value)
            else:
                oa_works = await self.openalex.search_works_by_name(profile.normalized_name)

            for work in oa_works:
                if not verified_openalex and not self._is_vignan_work_openalex(work):
                    continue
                await self._process_openalex_work(profile, work, stats, is_verified_author=bool(verified_openalex))
            stats["sources_queried"]["openalex"] = stats["sources_queried"].get("openalex", 0) + 1
        except Exception as e:
            logger.error(f"Error in OpenAlex discovery for {profile.normalized_name}: {e}")
            stats["errors"] += 1

        # --- 2. Crossref ---
        try:
            cr_works = await self.crossref.search_works_by_author(profile.normalized_name, "Vignan")
            for work in cr_works:
                await self._process_crossref_work(profile, work, stats)
            stats["sources_queried"]["crossref"] = stats["sources_queried"].get("crossref", 0) + 1
        except Exception as e:
            logger.error(f"Error in Crossref discovery for {profile.normalized_name}: {e}")
            stats["errors"] += 1

        # --- 3. Scopus (if API key configured) ---
        if self.scopus.enabled:
            try:
                verified_scopus = next((i for i in identifiers if i.identifier_type == "scopus" and i.verified), None)
                if verified_scopus:
                    scopus_entries = await self.scopus.search_author_works(verified_scopus.identifier_value)
                else:
                    scopus_entries = await self.scopus.search_publications(profile.normalized_name, "Vignan")
                for entry in scopus_entries:
                    await self._process_scopus_work(profile, entry, stats, is_verified_author=bool(verified_scopus))
                stats["sources_queried"]["scopus"] = stats["sources_queried"].get("scopus", 0) + 1
            except Exception as e:
                logger.error(f"Error in Scopus discovery for {profile.normalized_name}: {e}")
                stats["errors"] += 1

        # --- 4. IEEE Xplore (if API key configured) ---
        if self.ieee.enabled:
            try:
                verified_ieee = next((i for i in identifiers if i.identifier_type == "ieee" and i.verified), None)
                if verified_ieee:
                    ieee_articles = await self.ieee.get_author_works(verified_ieee.identifier_value)
                else:
                    ieee_articles = await self.ieee.search_publications(profile.normalized_name, "Vignan")
                for article in ieee_articles:
                    await self._process_ieee_work(profile, article, stats, is_verified_author=bool(verified_ieee))
                stats["sources_queried"]["ieee"] = stats["sources_queried"].get("ieee", 0) + 1
            except Exception as e:
                logger.error(f"Error in IEEE discovery for {profile.normalized_name}: {e}")
                stats["errors"] += 1

        # --- 5. Semantic Scholar ---
        try:
            s2_papers = await self.semantic_scholar.search_papers(profile.normalized_name)
            for paper in s2_papers:
                await self._process_s2_work(profile, paper, stats)
            stats["sources_queried"]["semantic_scholar"] = stats["sources_queried"].get("semantic_scholar", 0) + 1
        except Exception as e:
            logger.error(f"Error in Semantic Scholar discovery for {profile.normalized_name}: {e}")
            stats["errors"] += 1

        # --- 6. ORCID (if faculty has verified ORCID identifier) ---
        try:
            verified_orcid = next((i for i in identifiers if i.identifier_type == "orcid" and i.verified), None)
            if verified_orcid:
                orcid_works = await self.orcid.get_works(verified_orcid.identifier_value)
                for work in orcid_works:
                    await self._process_orcid_work(profile, work, stats, is_verified_author=True)
                stats["sources_queried"]["orcid"] = stats["sources_queried"].get("orcid", 0) + 1
        except Exception as e:
            logger.error(f"Error in ORCID discovery for {profile.normalized_name}: {e}")
            stats["errors"] += 1

        # --- 7. Vidwan (if faculty has verified Vidwan identifier) ---
        try:
            verified_vidwan = next((i for i in identifiers if i.identifier_type == "vidwan" and i.verified), None)
            if verified_vidwan:
                vidwan_works = await self.vidwan.get_profile_publications(verified_vidwan.identifier_value)
                for work in vidwan_works:
                    await self._process_vidwan_work(profile, work, stats, is_verified_author=True)
                stats["sources_queried"]["vidwan"] = stats["sources_queried"].get("vidwan", 0) + 1
        except Exception as e:
            logger.error(f"Error in Vidwan discovery for {profile.normalized_name}: {e}")
            stats["errors"] += 1

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
            PublicationSource.source_id.ilike(str(source_id).strip())
        )
        existing = await self.session.execute(stmt)
        return existing.scalars().first() is not None

    def _extract_authors_from_metadata(self, source_system: str, raw_metadata: dict) -> tuple[list | None, str | None]:
        """Extract parsed authors and raw authors string from source metadata."""
        parsed_authors = []
        raw_names = []

        if source_system == "openalex":
            authorships = raw_metadata.get("authorships", [])
            for i, auth in enumerate(authorships):
                author_data = auth.get("author", {}) or {}
                name = author_data.get("display_name", "").strip()
                if name:
                    raw_names.append(name)
                    affils = [inst.get("display_name") for inst in auth.get("institutions", []) if inst.get("display_name")]
                    parsed_authors.append({
                        "name": name,
                        "position": i + 1,
                        "affiliations": affils,
                    })
        elif source_system == "crossref":
            authors = raw_metadata.get("author", [])
            for i, auth in enumerate(authors):
                given = auth.get("given", "").strip()
                family = auth.get("family", "").strip()
                name = f"{given} {family}".strip() if (given or family) else auth.get("name", "").strip()
                if name:
                    raw_names.append(name)
                    affils = [a.get("name") for a in auth.get("affiliation", []) if a.get("name")]
                    parsed_authors.append({
                        "name": name,
                        "position": i + 1,
                        "affiliations": affils,
                    })
        elif source_system == "semantic_scholar":
            authors = raw_metadata.get("authors", [])
            for i, auth in enumerate(authors):
                name = auth.get("name", "").strip()
                if name:
                    raw_names.append(name)
                    parsed_authors.append({
                        "name": name,
                        "position": i + 1,
                        "affiliations": [],
                    })
        elif source_system == "scopus":
            creator = raw_metadata.get("dc:creator")
            if creator:
                raw_names.append(creator)
                parsed_authors.append({
                    "name": creator,
                    "position": 1,
                    "affiliations": [],
                })
        elif source_system == "ieee":
            authors_data = raw_metadata.get("authors", {}).get("authors", []) or []
            for i, auth in enumerate(authors_data):
                name = auth.get("full_name") or auth.get("preferred_name") or f"{auth.get('first_name', '')} {auth.get('last_name', '')}".strip()
                if name:
                    raw_names.append(name)
                    affil = auth.get("affiliation")
                    parsed_authors.append({
                        "name": name,
                        "position": i + 1,
                        "affiliations": [affil] if affil else [],
                    })

        authors_raw_str = ", ".join(raw_names) if raw_names else None
        return (parsed_authors if parsed_authors else None, authors_raw_str)

    async def _create_publication(
        self, profile: FacultyProfile, title: str, doi: str | None,
        year: int | None, source_system: str, source_id: str,
        raw_metadata: dict, stats: Dict[str, Any],
        is_verified_author: bool = False
    ):
        """Find or create a Publication + attach PublicationSource (+ link PublicationAuthor if verified author)."""
        clean_doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip().lower() if doi else None

        # Clean normalized title
        norm_title = re.sub(r"<[^>]+>", "", title or "")
        norm_title = re.sub(r"[^\w\s]", "", norm_title.lower())
        norm_title = " ".join(norm_title.split())[:255]

        # 1. Check if publication already exists by DOI or normalized title
        pub = None
        if clean_doi:
            stmt = select(Publication).options(
                selectinload(Publication.authors),
                selectinload(Publication.sources)
            ).where(Publication.doi.ilike(clean_doi))
            res = await self.session.execute(stmt)
            pub = res.scalars().first()

        if not pub and norm_title and norm_title != "unknown title":
            stmt = select(Publication).options(
                selectinload(Publication.authors),
                selectinload(Publication.sources)
            ).where(
                (Publication.normalized_title == norm_title) |
                (Publication.title.ilike((title or '').strip()))
            )
            res = await self.session.execute(stmt)
            pub = res.scalars().first()

        if not pub and norm_title and len(norm_title) >= 15:
            prefix = norm_title[:40]
            stmt = select(Publication).options(
                selectinload(Publication.authors),
                selectinload(Publication.sources)
            ).where(Publication.normalized_title.ilike(f"%{prefix}%"))
            res = await self.session.execute(stmt)
            for candidate in res.scalars().all():
                if fuzz.ratio(candidate.normalized_title or "", norm_title) >= 80:
                    pub = candidate
                    break

        parsed_authors, authors_raw_str = self._extract_authors_from_metadata(source_system, raw_metadata)

        if pub:
            pub_id = pub.id
            # Update fields if missing
            if clean_doi and not pub.doi:
                pub.doi = clean_doi
            if year and not pub.year:
                pub.year = year
            if parsed_authors and not pub.authors_parsed:
                pub.authors_parsed = parsed_authors
            if authors_raw_str and not pub.authors_raw:
                pub.authors_raw = authors_raw_str
        else:
            pub_id = uuid.uuid4()
            pub = Publication(
                id=pub_id,
                title=title,
                normalized_title=norm_title,
                doi=clean_doi,
                year=year,
                authors_parsed=parsed_authors,
                authors_raw=authors_raw_str,
                publication_type="journal-article" if source_system in ("openalex", "crossref", "ieee", "scopus") else "other",
                verification_status="verified",
                attribution_confidence=1.0 if is_verified_author else 0.80,
                metadata_confidence=1.0,
                risk_level="none",
            )
            self.session.add(pub)
            await self.session.flush()
            stats["publications_discovered"] += 1
            if clean_doi:
                stats["dois_found"] += 1

        # 2. Attach source if not already present
        clean_sid = str(source_id).strip()
        src_stmt = select(PublicationSource).where(
            PublicationSource.publication_id == pub_id,
            PublicationSource.source_system == source_system,
            PublicationSource.source_id.ilike(clean_sid)
        )
        src_existing = (await self.session.execute(src_stmt)).scalars().first()
        if not src_existing:
            src = PublicationSource(
                id=uuid.uuid4(),
                publication_id=pub_id,
                source_system=source_system,
                source_id=clean_sid,
                raw_metadata=raw_metadata,
                discovery_method=f"{source_system}_api"
            )
            self.session.add(src)

        # 3. If discovered via a verified author identifier, link PublicationAuthor
        if is_verified_author:
            auth_stmt = select(PublicationAuthor).where(
                PublicationAuthor.publication_id == pub_id,
                PublicationAuthor.faculty_id == profile.id
            )
            auth_existing = (await self.session.execute(auth_stmt)).scalars().first()
            if not auth_existing:
                pub_auth = PublicationAuthor(
                    id=uuid.uuid4(),
                    publication_id=pub_id,
                    faculty_id=profile.id,
                    author_position=1,
                    author_name_raw=profile.raw_name,
                    attribution_confidence=1.0,
                    attribution_method=f"{source_system}_author_id_verified",
                    is_corresponding=False,
                )
                self.session.add(pub_auth)

        # 4. Provenance
        prov = ProvenanceRecord(
            entity_type="publication",
            entity_id=pub_id,
            event_type="discovered",
            source=source_system,
            detail=f"Discovered via {source_system} search for {profile.normalized_name}",
            agent_name="PublicationDiscoveryAgent"
        )
        self.session.add(prov)

    async def _process_openalex_work(self, profile: FacultyProfile, work: Dict[str, Any], stats: Dict[str, Any], is_verified_author: bool = False):
        source_id = work.get("id")
        if not source_id:
            return
        clean_sid = str(source_id).strip()
        if await self._check_source_exists("openalex", clean_sid):
            stats["duplicates_prevented"] += 1
            return
        doi = work.get("doi")
        if doi:
            doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip().lower()
        title = work.get("title") or "Unknown Title"
        year = work.get("publication_year")
        await self._create_publication(profile, title, doi, year, "openalex", clean_sid, work, stats, is_verified_author=is_verified_author)

    async def _process_crossref_work(self, profile: FacultyProfile, work: Dict[str, Any], stats: Dict[str, Any]):
        doi = work.get("DOI")
        if not doi:
            return
        clean_doi = str(doi).replace("https://doi.org/", "").replace("http://doi.org/", "").strip().lower()
        if await self._check_source_exists("crossref", clean_doi):
            stats["duplicates_prevented"] += 1
            return
        titles = work.get("title", [])
        title = titles[0] if titles else "Unknown Title"
        year = None
        issued = work.get("issued", {})
        date_parts = issued.get("date-parts", [[]])
        if date_parts and date_parts[0]:
            year = date_parts[0][0]
        await self._create_publication(profile, title, clean_doi, year, "crossref", clean_doi, work, stats, is_verified_author=False)

    async def _process_scopus_work(self, profile: FacultyProfile, entry: Dict[str, Any], stats: Dict[str, Any], is_verified_author: bool = False):
        """Process a Scopus search result entry."""
        data = self.scopus.extract_publication_data(entry)
        source_id = data.get("eid") or data.get("scopus_id")
        if not source_id:
            return
        clean_sid = str(source_id).strip()
        if await self._check_source_exists("scopus", clean_sid):
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
        await self._create_publication(profile, title, doi, year, "scopus", clean_sid, entry, stats, is_verified_author=is_verified_author)

    async def _process_ieee_work(self, profile: FacultyProfile, article: Dict[str, Any], stats: Dict[str, Any], is_verified_author: bool = False):
        """Process an IEEE Xplore article result."""
        data = self.ieee.extract_article_data(article)
        source_id = data.get("source_publication_id") or data.get("doi")
        if not source_id:
            return
        clean_sid = str(source_id).strip()
        if await self._check_source_exists("ieee", clean_sid):
            stats["duplicates_prevented"] += 1
            return
        doi = data.get("doi")
        title = data.get("title") or "Unknown Title"
        year = data.get("year")
        await self._create_publication(profile, title, doi, year, "ieee", clean_sid, article, stats, is_verified_author=is_verified_author)

    async def _process_s2_work(self, profile: FacultyProfile, paper: Dict[str, Any], stats: Dict[str, Any]):
        """Process a Semantic Scholar paper result."""
        data = self.semantic_scholar.extract_paper_data(paper)
        source_id = data.get("s2_paper_id")
        if not source_id:
            return
        clean_sid = str(source_id).strip()
        if await self._check_source_exists("semantic_scholar", clean_sid):
            stats["duplicates_prevented"] += 1
            return
        doi = data.get("doi")
        title = data.get("title") or "Unknown Title"
        year = data.get("year")
        await self._create_publication(profile, title, doi, year, "semantic_scholar", clean_sid, paper, stats, is_verified_author=False)

    async def _process_orcid_work(self, profile: FacultyProfile, work_summary: Dict[str, Any], stats: Dict[str, Any], is_verified_author: bool = True):
        """Process an ORCID work-summary."""
        data = self.orcid.extract_work_data(work_summary)
        put_code = data.get("orcid_put_code")
        source_id = f"orcid:{put_code}" if put_code else None
        if not source_id:
            return
        clean_sid = str(source_id).strip()
        if await self._check_source_exists("orcid", clean_sid):
            stats["duplicates_prevented"] += 1
            return
        doi = data.get("doi")
        title = data.get("title") or "Unknown Title"
        year = data.get("year")
        await self._create_publication(profile, title, doi, year, "orcid", clean_sid, work_summary, stats, is_verified_author=is_verified_author)

    async def _process_vidwan_work(self, profile: FacultyProfile, work: Dict[str, Any], stats: Dict[str, Any], is_verified_author: bool = True):
        """Process a Vidwan public profile publication result."""
        source_id = work.get("source_id") or work.get("doi")
        if not source_id:
            return
        clean_sid = str(source_id).strip()
        if await self._check_source_exists("vidwan", clean_sid):
            stats["duplicates_prevented"] += 1
            return
        doi = work.get("doi")
        title = work.get("title") or "Unknown Title"
        year = work.get("year")
        await self._create_publication(profile, title, doi, year, "vidwan", clean_sid, work, stats, is_verified_author=is_verified_author)
