import logging
from typing import Dict, Any, Tuple, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from rapidfuzz import fuzz
import uuid

from app.models.faculty import FacultyProfile, FacultyIdentifier
from app.models.review import ReviewTask
from app.models.provenance import ProvenanceRecord
from app.models.affiliation import AffiliationVariant
from app.connectors.openalex import OpenAlexClient
from app.connectors.orcid import OrcidClient
from app.connectors.scopus import ScopusClient
from app.config import get_settings

logger = logging.getLogger(__name__)

# Default VFSTR affiliations (fallback if DB table is empty)
_DEFAULT_AFFILIATIONS = [
    "Vignan's Foundation for Science, Technology & Research",
    "Vignan's Foundation for Science Technology and Research",
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

class FacultyIdentityAgent:
    """Agent 1 - Faculty Identity Resolution"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        settings = get_settings()
        self.openalex = OpenAlexClient(email=settings.openalex_email)
        self.orcid = OrcidClient(client_id=settings.orcid_client_id, client_secret=settings.orcid_client_secret)
        self.scopus = ScopusClient(api_key=settings.scopus_api_key, inst_token=settings.scopus_inst_token)
        self.affiliation_variants: List[str] = []

    async def _load_affiliation_variants(self):
        """Load affiliation variants from database, fallback to defaults."""
        try:
            result = await self.session.execute(select(AffiliationVariant.variant_text))
            db_variants = [row[0] for row in result.all()]
            if db_variants:
                self.affiliation_variants = db_variants
                return
        except Exception as e:
            logger.warning(f"Could not load affiliation variants from DB: {e}")
        self.affiliation_variants = _DEFAULT_AFFILIATIONS

    async def run(self) -> Dict[str, Any]:
        """Runs the identity resolution process for all active faculty."""
        logger.info("Starting Faculty Identity Resolution (Phase 3 — Multi-Source)")
        
        await self._load_affiliation_variants()
        
        stmt = select(FacultyProfile).options(
            selectinload(FacultyProfile.name_variants),
            selectinload(FacultyProfile.identifiers)
        ).where(FacultyProfile.status == "active")
        
        result = await self.session.execute(stmt)
        profiles = result.scalars().all()
        
        stats = {
            "processed": 0,
            "matched": 0,
            "ambiguous": 0,
            "unmatched": 0,
            "orcid_resolved": 0,
            "scopus_resolved": 0,
            "errors": 0
        }
        
        for profile in profiles:
            stats["processed"] += 1
            
            # --- OpenAlex Resolution ---
            has_openalex = any(i.identifier_type == "openalex" and i.verified for i in profile.identifiers)
            if not has_openalex:
                try:
                    candidates = await self.openalex.search_authors(profile.normalized_name)
                    best_candidate, confidence = self._rank_candidates(profile, candidates)
                    
                    if best_candidate:
                        openalex_id = best_candidate.get("id")
                        if confidence >= 0.85:
                            await self._record_identity(profile, "openalex", openalex_id, confidence, True)
                            stats["matched"] += 1
                        elif confidence >= 0.60:
                            await self._record_identity(profile, "openalex", openalex_id, confidence, False)
                            await self._create_review_task(profile, best_candidate, confidence)
                            stats["ambiguous"] += 1
                        else:
                            stats["unmatched"] += 1
                    else:
                        stats["unmatched"] += 1
                except Exception as e:
                    logger.error(f"Error in OpenAlex resolution for {profile.id}: {e}")
                    stats["errors"] += 1

            # --- ORCID Resolution ---
            has_orcid = any(i.identifier_type == "orcid" and i.verified for i in profile.identifiers)
            if not has_orcid:
                try:
                    orcid_results = await self.orcid.search_by_name(profile.normalized_name, "Vignan")
                    for result_entry in orcid_results[:3]:  # Check top 3 candidates
                        profile_data = self.orcid.extract_profile_data(result_entry)
                        orcid_id = profile_data.get("orcid_id")
                        if not orcid_id:
                            continue
                        # Verify affiliation match
                        institutions = profile_data.get("institution_names", [])
                        affil_match = any(
                            any(fuzz.partial_ratio(v.lower(), inst.lower()) > 75 for v in self.affiliation_variants)
                            for inst in institutions
                        ) if institutions else False
                        # Verify name match
                        full_name = f"{profile_data.get('given_names', '')} {profile_data.get('family_name', '')}".strip()
                        name_score = fuzz.token_set_ratio(profile.normalized_name, full_name.lower()) / 100.0
                        if name_score >= 0.80 and affil_match:
                            await self._record_identity(profile, "orcid", orcid_id, name_score, True)
                            stats["orcid_resolved"] += 1
                            break
                        elif name_score >= 0.65:
                            await self._record_identity(profile, "orcid", orcid_id, name_score, False)
                            stats["orcid_resolved"] += 1
                            break
                except Exception as e:
                    logger.error(f"Error in ORCID resolution for {profile.id}: {e}")
                    stats["errors"] += 1

            # --- Scopus Author ID Resolution (if enabled) ---
            has_scopus = any(i.identifier_type == "scopus" and i.verified for i in profile.identifiers)
            if not has_scopus and self.scopus.enabled:
                try:
                    scopus_authors = await self.scopus.search_author(profile.normalized_name, "Vignan")
                    for entry in scopus_authors[:3]:
                        author_data = self.scopus.extract_author_data(entry)
                        scopus_id = author_data.get("scopus_author_id")
                        if not scopus_id:
                            continue
                        affil_name = author_data.get("affiliation", "")
                        affil_match = any(
                            fuzz.partial_ratio(v.lower(), affil_name.lower()) > 75
                            for v in self.affiliation_variants
                        ) if affil_name else False
                        if affil_match:
                            await self._record_identity(profile, "scopus", scopus_id, 0.85, True)
                            stats["scopus_resolved"] += 1
                            break
                except Exception as e:
                    logger.error(f"Error in Scopus resolution for {profile.id}: {e}")
                    stats["errors"] += 1
                
        await self.session.commit()
        return stats

    def _rank_candidates(self, profile: FacultyProfile, candidates: list[Dict[str, Any]]) -> Tuple[Dict[str, Any] | None, float]:
        best_candidate = None
        best_score = 0.0
        
        target_names = [profile.normalized_name.lower()]
        for nv in profile.name_variants:
            target_names.append(nv.name_variant.lower())
            
        for candidate in candidates:
            cand_name = candidate.get("display_name", "").lower()
            if not cand_name:
                continue
                
            # Score Name Match
            name_score = 0.0
            for t_name in target_names:
                score = fuzz.ratio(t_name, cand_name) / 100.0
                if score > name_score:
                    name_score = score
                    
            if name_score < 0.50:
                continue
                
            # Score Affiliation
            affil_score = 0.0
            last_known = candidate.get("last_known_institution")
            if last_known and last_known.get("display_name"):
                cand_affil = last_known.get("display_name").lower()
                for vfstr in self.affiliation_variants:
                    # Token set ratio handles subsets well
                    match = fuzz.token_set_ratio(vfstr.lower(), cand_affil) / 100.0
                    if match > affil_score:
                        affil_score = match
                        
            # Combined Confidence (Base name + boost for affiliation)
            # If name is perfect (1.0), and affiliation matches (0.9), total = ~0.95
            confidence = (name_score * 0.6) + (affil_score * 0.4)
            
            # If we don't have affiliation data, we cap confidence
            if affil_score == 0.0:
                confidence = name_score * 0.7  # Cap at 0.7
                
            if confidence > best_score:
                best_score = confidence
                best_candidate = candidate
                
        return best_candidate, best_score

    async def _record_identity(self, profile: FacultyProfile, identifier_type: str, identifier_value: str, confidence: float, verified: bool):
        # Check if exists
        for i in profile.identifiers:
            if i.identifier_type == identifier_type and i.identifier_value == identifier_value:
                return

        ident_id = uuid.uuid4()
        ident = FacultyIdentifier(
            id=ident_id,
            faculty_id=profile.id,
            identifier_type=identifier_type,
            identifier_value=identifier_value,
            verified=verified,
            verification_source="Agent 1 (IdentityAgent)",
            confidence=confidence
        )
        self.session.add(ident)
        
        prov = ProvenanceRecord(
            entity_type="identifier",
            entity_id=ident_id,
            event_type="discovered",
            source=identifier_type,
            detail=f"Discovered {identifier_type} ID {identifier_value} with confidence {confidence:.2f}",
            confidence=confidence,
            agent_name="FacultyIdentityAgent"
        )
        self.session.add(prov)

    async def _create_review_task(self, profile: FacultyProfile, candidate: dict, confidence: float):
        explanation = (
            f"Found potential OpenAlex identity ({candidate.get('id')}) for {profile.raw_name}. "
            f"Confidence: {confidence:.2f}. "
            f"Name matched: {candidate.get('display_name')}. "
        )
        last_inst = candidate.get('last_known_institution')
        if last_inst:
            explanation += f"Last known institution: {last_inst.get('display_name')}."
            
        task = ReviewTask(
            task_type="IDENTIFIER_MATCH",
            priority="medium",
            entity_type="faculty",
            entity_id=profile.id,
            explanation=explanation,
            evidence={
                "candidate": candidate,
                "confidence": confidence
            },
            options=[
                {"action": "CONFIRM", "label": "Yes, this is the correct OpenAlex ID"},
                {"action": "REJECT", "label": "No, incorrect ID"}
            ],
            agent_name="FacultyIdentityAgent"
        )
        self.session.add(task)
