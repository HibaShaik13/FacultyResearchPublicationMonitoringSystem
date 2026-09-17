import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from rapidfuzz import fuzz
import html
import re

from app.models.faculty import FacultyProfile, FacultyIdentifier
from app.models.review import ReviewTask
from app.models.provenance import ProvenanceRecord
from app.models.affiliation import AffiliationVariant
from app.connectors.openalex import OpenAlexClient
from app.connectors.orcid import OrcidClient
from app.connectors.scopus import ScopusClient
from app.connectors.ieee import IEEEClient
from app.config import get_settings

logger = logging.getLogger(__name__)

# Canonical VFSTR variations (Vadlamudi / Guntur University)
_DEFAULT_VFSTR_AFFILIATIONS = [
    "Vignan's Foundation for Science, Technology & Research",
    "Vignan Foundation for Science, Technology and Research",
    "VFSTR",
    "VFSTR Deemed to be University",
    "Vignan University",
    "Vignan's University",
    "Vignans Foundation for Science Technology and Research",
    "Vignan's Engineering College, Vadlamudi",
    "Vignan, Vadlamudi",
    "Vignan, Guntur",
]


class FacultyIdentityAgent:
    """Agent 1 - Faculty Identity & External Researcher Identity Resolution"""

    def __init__(self, session: AsyncSession):
        self.session = session
        settings = get_settings()
        self.openalex = OpenAlexClient(email=settings.openalex_email)
        self.orcid = OrcidClient(client_id=settings.orcid_client_id, client_secret=settings.orcid_client_secret)
        self.scopus = ScopusClient(api_key=settings.scopus_api_key, inst_token=settings.scopus_inst_token)
        self.ieee = IEEEClient(api_key=settings.ieee_api_key)
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
        self.affiliation_variants = _DEFAULT_VFSTR_AFFILIATIONS

    def _classify_institution_affinity(self, affiliation_str: str) -> str:
        """
        Strictly classify institutional affinity:
        - 'VFSTR': Canonical VFSTR University at Vadlamudi / Guntur
        - 'SIBLING_VIGNAN': Sister colleges (Lara, VITS Hyd, VIIT Vizag, Nirula, Pharmacy)
        - 'EXTERNAL': Non-Vignan or Unknown
        """
        if not affiliation_str:
            return "EXTERNAL"

        clean = html.unescape(str(affiliation_str)).lower().replace("’", "'").replace("´", "'")

        if any(sibling in clean for sibling in [
            "lara", "vlits", "deshmukhi", "hyderabad", "nalgonda",
            "duvvada", "visakhapatnam", "vizag", "nirula", "pharmacy college"
        ]):
            return "SIBLING_VIGNAN"

        if any(vfstr in clean for vfstr in [
            "vignan's foundation", "vfstr", "vignan foundation",
            "deemed to be university", "deemed university", "vadlamudi", "vignan university",
            "vignan's university"
        ]):
            return "VFSTR"

        if "vignan" in clean:
            return "GENERIC_VIGNAN"

        return "EXTERNAL"

    def _has_forename_contradiction(self, candidate_name: str, profile: FacultyProfile) -> bool:
        """Prevent false matches between distinct forenames."""
        c_lower = candidate_name.lower().strip()
        p_raw = profile.raw_name.lower().replace("dr.", "").replace("dr", "").replace("prof.", "").replace("prof", "").strip()

        c_tokens = set(re.findall(r'[a-z]+', c_lower))
        p_tokens = set(re.findall(r'[a-z]+', p_raw))

        # Siva / Shiva Prasad checks
        if "siva" in p_raw or "shiva" in p_raw:
            contradicting_tokens = [
                "sai", "deva", "durga", "syam", "bhanu", "sarkale", "lalith", "rohit",
                "bharat", "ganesh", "eppe", "anjaneya", "eswara", "kiran", "deepika",
                "sravanthi", "mouli", "kanaka", "koteswara", "balakrishna", "krishna",
                "vara", "leela", "ramanjan", "chandra", "phanindra", "divya", "naga"
            ]
            if any(t in c_tokens for t in contradicting_tokens) and ("siva" not in c_tokens and "shiva" not in c_tokens):
                return True

        # Umadevi vs Uma / others
        if "umadevi" in p_raw:
            if any(t in c_tokens for t in ["mahesh", "shankar", "kiran", "reddy", "kumar", "singh", "sharma"]):
                if "umadevi" not in c_tokens:
                    return True

        # Check leading single-letter initial contradiction (e.g. 'M. Siva Prasad' vs 'P. Siva Prasad')
        c_parts = [p.replace(".", "").strip() for p in c_lower.split() if p.replace(".", "").strip()]
        p_parts = [p.replace(".", "").strip() for p in p_raw.split() if p.replace(".", "").strip()]
        if c_parts and p_parts:
            if len(c_parts[0]) == 1 and len(p_parts[0]) == 1 and c_parts[0] != p_parts[0]:
                return True

        return False

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
            "ieee_resolved": 0,
            "errors": 0
        }

        for profile in profiles:
            stats["processed"] += 1

            # --- 1. OpenAlex Resolution ---
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
                            await self._create_review_task(profile, best_candidate, confidence, "openalex")
                            stats["ambiguous"] += 1
                        else:
                            stats["unmatched"] += 1
                    else:
                        stats["unmatched"] += 1
                except Exception as e:
                    logger.error(f"Error in OpenAlex resolution for {profile.id}: {e}")
                    stats["errors"] += 1

            # --- 2. ORCID Resolution ---
            has_orcid = any(i.identifier_type == "orcid" and i.verified for i in profile.identifiers)
            if not has_orcid:
                try:
                    orcid_results = await self.orcid.search_by_name(profile.normalized_name, "Vignan")
                    for result_entry in orcid_results[:3]:
                        profile_data = self.orcid.extract_profile_data(result_entry)
                        orcid_id = profile_data.get("orcid_id")
                        if not orcid_id:
                            continue

                        full_name = f"{profile_data.get('given_names', '')} {profile_data.get('family_name', '')}".strip()
                        if self._has_forename_contradiction(full_name, profile):
                            continue

                        institutions = profile_data.get("institution_names", [])
                        inst_category = "EXTERNAL"
                        for inst in institutions:
                            cat = self._classify_institution_affinity(inst)
                            if cat == "VFSTR":
                                inst_category = "VFSTR"
                                break
                            elif cat == "SIBLING_VIGNAN":
                                inst_category = "SIBLING_VIGNAN"

                        name_score = fuzz.token_set_ratio(profile.normalized_name, full_name.lower()) / 100.0

                        if inst_category == "SIBLING_VIGNAN":
                            name_score = max(0.0, name_score - 0.40)
                        elif inst_category == "VFSTR" and name_score >= 0.75:
                            name_score = min(1.0, name_score + 0.20)

                        if name_score >= 0.85:
                            await self._record_identity(profile, "orcid", orcid_id, name_score, True)
                            stats["orcid_resolved"] += 1
                            break
                        elif name_score >= 0.60:
                            await self._record_identity(profile, "orcid", orcid_id, name_score, False)
                            await self._create_review_task(profile, {"id": orcid_id, "display_name": full_name}, name_score, "orcid")
                            stats["ambiguous"] += 1
                            break
                except Exception as e:
                    logger.error(f"Error in ORCID resolution for {profile.id}: {e}")
                    stats["errors"] += 1

            # --- 3. Scopus Author ID Resolution ---
            has_scopus = any(i.identifier_type == "scopus" and i.verified for i in profile.identifiers)
            if not has_scopus and self.scopus.enabled:
                try:
                    scopus_authors = await self.scopus.search_author(profile.normalized_name, "Vignan")
                    for entry in scopus_authors[:3]:
                        author_data = self.scopus.extract_author_data(entry)
                        scopus_id = author_data.get("scopus_author_id")
                        if not scopus_id:
                            continue

                        cand_name = author_data.get("name", "")
                        if self._has_forename_contradiction(cand_name, profile):
                            continue

                        affil_name = author_data.get("affiliation", "")
                        inst_cat = self._classify_institution_affinity(affil_name)

                        name_score = fuzz.token_set_ratio(profile.normalized_name, cand_name.lower()) / 100.0
                        if inst_cat == "SIBLING_VIGNAN":
                            name_score = max(0.0, name_score - 0.40)
                        elif inst_cat == "VFSTR" and name_score >= 0.75:
                            name_score = min(1.0, name_score + 0.20)

                        if name_score >= 0.85:
                            await self._record_identity(profile, "scopus", scopus_id, name_score, True)
                            stats["scopus_resolved"] += 1
                            break
                except Exception as e:
                    logger.error(f"Error in Scopus resolution for {profile.id}: {e}")
                    stats["errors"] += 1

            # --- 4. IEEE Xplore Author ID Resolution ---
            has_ieee = any(i.identifier_type == "ieee" and i.verified for i in profile.identifiers)
            if not has_ieee and self.ieee.enabled:
                try:
                    ieee_articles = await self.ieee.search_publications(profile.normalized_name, "Vignan")
                    for art in ieee_articles[:3]:
                        for auth in (art.get("authors", {}).get("authors", []) or []):
                            auth_name = auth.get("full_name") or f"{auth.get('first_name', '')} {auth.get('last_name', '')}".strip()
                            auth_id = auth.get("id")
                            if auth_id and not self._has_forename_contradiction(auth_name, profile):
                                affil = auth.get("affiliation", "")
                                inst_cat = self._classify_institution_affinity(affil)
                                if inst_cat == "VFSTR":
                                    await self._record_identity(profile, "ieee", str(auth_id), 0.95, True)
                                    stats["ieee_resolved"] += 1
                                    break
                except Exception as e:
                    logger.error(f"Error in IEEE resolution for {profile.id}: {e}")
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

            if self._has_forename_contradiction(cand_name, profile):
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
                cand_affil = last_known.get("display_name")
                inst_cat = self._classify_institution_affinity(cand_affil)
                if inst_cat == "VFSTR":
                    affil_score = 1.0
                elif inst_cat == "GENERIC_VIGNAN":
                    affil_score = 0.5
                elif inst_cat == "SIBLING_VIGNAN":
                    affil_score = -0.5

            confidence = (name_score * 0.6) + (max(0.0, affil_score) * 0.4)
            if affil_score < 0.0:
                confidence = max(0.0, confidence - 0.40)
            elif affil_score == 0.0:
                confidence = name_score * 0.7

            if confidence > best_score:
                best_score = confidence
                best_candidate = candidate

        return best_candidate, best_score

    async def _record_identity(
        self,
        profile: FacultyProfile,
        identifier_type: str,
        identifier_value: str,
        confidence: float,
        verified: bool
    ):
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

    async def _create_review_task(
        self,
        profile: FacultyProfile,
        candidate: dict,
        confidence: float,
        source_system: str
    ):
        explanation = (
            f"Found potential {source_system.upper()} identity ({candidate.get('id')}) for {profile.raw_name}. "
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
                "confidence": confidence,
                "source": source_system
            },
            options=[
                {"action": "CONFIRM", "label": f"Yes, this is my {source_system.upper()} ID"},
                {"action": "REJECT", "label": "No, incorrect ID"}
            ],
            agent_name="FacultyIdentityAgent"
        )
        self.session.add(task)
