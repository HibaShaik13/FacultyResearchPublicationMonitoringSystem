import logging
import uuid
import re
import html
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from rapidfuzz import fuzz

from app.models.publication import Publication, PublicationAuthor
from app.models.faculty import FacultyProfile
from app.models.review import ReviewTask
from app.models.provenance import ProvenanceRecord
from app.models.affiliation import AffiliationVariant

logger = logging.getLogger(__name__)

# Default affiliation keywords (fallback)
_DEFAULT_AFFIL_KEYWORDS = ["vignan", "vfstr", "science, technology & research"]

class FacultyAttributionAgent:
    """Agent 6 - Faculty Attribution"""
    AUTO_ATTRIBUTION_THRESHOLD = 0.95
    AMBIGUOUS_THRESHOLD = 0.60
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.faculty_cache = []
        self.affiliation_keywords: List[str] = []

    async def _load_faculty(self):
        stmt = select(FacultyProfile).options(
            selectinload(FacultyProfile.name_variants),
            selectinload(FacultyProfile.identifiers)
        ).where(FacultyProfile.status == "active")
        result = await self.session.execute(stmt)
        self.faculty_cache = result.scalars().unique().all()

    async def run(self) -> Dict[str, Any]:
        logger.info("Starting Faculty Attribution (Phase 6 - Agent 6)")
        
        await self._load_faculty()
        await self._load_affiliation_keywords()
        
        # Load publications
        stmt = select(Publication).options(
            selectinload(Publication.authors),
            selectinload(Publication.sources)
        )
        result = await self.session.execute(stmt)
        publications = result.scalars().unique().all()
        
        stats = {
            "processed": 0,
            "attributions_created": 0,
            "high_confidence": 0,
            "ambiguous": 0,
            "errors": 0
        }
        
        for pub in publications:
            stats["processed"] += 1
            try:
                await self._process_publication(pub, stats)
            except Exception as e:
                logger.error(f"Error attributing publication {pub.id}: {e}")
                stats["errors"] += 1
                
        await self.session.commit()
        return stats

    async def _load_affiliation_keywords(self):
        """Load affiliation keywords from DB variants table."""
        try:
            result = await self.session.execute(select(AffiliationVariant.variant_text))
            db_variants = [row[0].lower() for row in result.all()]
            if db_variants:
                self.affiliation_keywords = db_variants
                return
        except Exception as e:
            logger.warning(f"Could not load affiliation variants: {e}")
        self.affiliation_keywords = _DEFAULT_AFFIL_KEYWORDS

    def _classify_institution_affinity(self, affiliations: List[str]) -> str:
        """
        Strictly classify institutional affinity:
        - 'VFSTR': Vignan's Foundation for Science, Technology & Research (Deemed University, Vadlamudi)
        - 'SIBLING_VIGNAN': Distinct sister institutions (Lara, VITS Hyderabad, VIIT Vizag, Nirula, Pharmacy)
        - 'EXTERNAL': Non-Vignan or Unknown
        """
        if not affiliations:
            return "EXTERNAL"

        import html
        combined = " ".join([html.unescape(str(a)).lower().replace("’", "'").replace("´", "'") for a in affiliations])

        # Distinct sibling colleges — must NOT match VFSTR University
        if any(sibling in combined for sibling in [
            "lara", "vlits", "deshmukhi", "hyderabad", "nalgonda", 
            "duvvada", "visakhapatnam", "vizag", "nirula", "pharmacy college"
        ]):
            return "SIBLING_VIGNAN"

        # Canonical VFSTR University matches
        if any(vfstr in combined for vfstr in [
            "vignan's foundation", "vfstr", "vignan foundation", 
            "deemed to be university", "deemed university", "vadlamudi", "vignan university",
            "vignan's university"
        ]):
            return "VFSTR"

        if "vignan" in combined:
            return "GENERIC_VIGNAN"

        return "EXTERNAL"

    def _parse_author_candidates(self, pub: Publication) -> List[Dict[str, Any]]:
        """Extract candidate author dicts prioritizing rich source metadata (affiliations, ORCID)."""
        import html
        candidates = []

        # 1. Sources with rich metadata (OpenAlex, Crossref)
        for src in (pub.sources or []):
            if not src.raw_metadata:
                continue
            if src.source_system == "openalex":
                authorships = src.raw_metadata.get("authorships", []) or []
                for i, auth in enumerate(authorships):
                    a_dict = auth.get("author") or {}
                    a_name = html.unescape(a_dict.get("display_name") or "").strip()
                    oa_id = str(a_dict.get("id") or "").strip()
                    orcid = str(a_dict.get("orcid") or "").strip()
                    if a_name:
                        affils = [html.unescape(inst.get("display_name")) for inst in (auth.get("institutions") or []) if inst and inst.get("display_name")]
                        candidates.append({
                            "name": a_name,
                            "openalex_id": oa_id,
                            "orcid": orcid,
                            "position": i + 1,
                            "affiliations": affils,
                        })
                if candidates:
                    return candidates
            elif src.source_system == "crossref":
                for i, auth in enumerate(src.raw_metadata.get("author") or []):
                    if not isinstance(auth, dict):
                        continue
                    given = html.unescape(str(auth.get("given") or "")).strip()
                    family = html.unescape(str(auth.get("family") or "")).strip()
                    name = f"{given} {family}".strip() if (given or family) else html.unescape(str(auth.get("name") or "")).strip()
                    orcid = str(auth.get("ORCID") or "").strip()
                    if name:
                        affils = [html.unescape(str(a.get("name") or "")) for a in (auth.get("affiliation") or []) if isinstance(a, dict) and a.get("name")]
                        candidates.append({
                            "name": name,
                            "orcid": orcid,
                            "position": i + 1,
                            "affiliations": affils,
                        })
                if candidates:
                    return candidates

        # 2. Parsed authors
        if pub.authors_parsed and isinstance(pub.authors_parsed, list):
            for i, ap in enumerate(pub.authors_parsed):
                if isinstance(ap, dict):
                    candidates.append(ap)
                elif isinstance(ap, str):
                    candidates.append({
                        "name": html.unescape(ap).strip(),
                        "position": i + 1,
                        "affiliations": [pub.affiliation_text] if pub.affiliation_text else [],
                    })
            if candidates:
                return candidates

        # 3. Fallback: parse from authors_raw string
        if pub.authors_raw:
            raw_splits = [html.unescape(a).strip() for a in pub.authors_raw.replace(";", ",").split(",") if a.strip()]
            for i, name in enumerate(raw_splits):
                candidates.append({
                    "name": name,
                    "position": i + 1,
                    "affiliations": [pub.affiliation_text] if pub.affiliation_text else [],
                })
            return candidates

        return candidates

    def _has_forename_contradiction(self, candidate_name: str, profile: FacultyProfile) -> bool:
        """Prevent false matches between distinct forenames (e.g., 'Sai' vs 'Siva', 'Deva' vs 'Siva')."""
        import re
        c_lower = candidate_name.lower().strip()
        p_raw = profile.raw_name.lower().replace("dr.", "").replace("dr", "").replace("prof.", "").replace("prof", "").strip()
        
        # Split tokens
        c_tokens = set(re.findall(r'[a-z]+', c_lower))
        p_tokens = set(re.findall(r'[a-z]+', p_raw))

        # Siva / Shiva Prasad checks
        if "siva" in p_raw or "shiva" in p_raw:
            contradicting_tokens = [
                "sai", "deva", "durga", "syam", "bhanu", "sarkale", "lalith", "rohit",
                "bharat", "ganesh", "eppe", "anjaneya", "eswara", "kiran", "deepika",
                "sravanthi", "mouli", "kanaka", "koteswara", "balakrishna", "krishna",
                "vara", "leela", "ramanjan", "chandra", "phanindra", "divya", "naga",
                "jyothi", "jyotshna", "pavani", "gandi", "motapotula", "somala"
            ]
            if any(t in c_tokens for t in contradicting_tokens) and ("siva" not in c_tokens and "shiva" not in c_tokens):
                return True

            # If middle/fore initial contradicts (e.g. 'P. E. Prasad', 'P. R. Prasad', 'M. Prasad')
            # Look for isolated single-letter initials in candidate name
            single_initials = set(re.findall(r'\b([a-z])\b', c_lower))
            # If candidate has initials other than 'p' and 's', and does not have 'siva'
            if single_initials - {'p', 's'} and ("siva" not in c_lower and "shiva" not in c_lower):
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

    async def _process_publication(self, pub: Publication, stats: Dict[str, Any]):
        author_candidates = self._parse_author_candidates(pub)
        if not author_candidates:
            return

        for author_data in author_candidates:
            raw_name = author_data.get("name", "")
            if not raw_name:
                continue
                
            norm_name = raw_name.lower().strip()
            affiliations = author_data.get("affiliations", []) or []
            if pub.affiliation_text and not affiliations:
                affiliations = [pub.affiliation_text]
            
            inst_category = self._classify_institution_affinity(affiliations)
            
            best_match_profile = None
            best_score = 0.0
            is_id_matched = False

            for profile in self.faculty_cache:
                # 1. Check External Author Identifier match (ORCID / OpenAlex ID / Scopus ID)
                c_orcid = author_data.get("orcid") or ""
                c_oa_id = author_data.get("openalex_id") or ""
                
                for ident in profile.identifiers:
                    if ident.identifier_type == "orcid" and ident.identifier_value and c_orcid:
                        if ident.identifier_value.lower() in c_orcid.lower():
                            best_score = 1.0
                            best_match_profile = profile
                            is_id_matched = True
                            break
                    if ident.identifier_type == "openalex" and ident.identifier_value and c_oa_id:
                        if ident.identifier_value.lower() in c_oa_id.lower():
                            best_score = 1.0
                            best_match_profile = profile
                            is_id_matched = True
                            break
                if is_id_matched:
                    break

                # 2. Check for explicit Forename Contradiction
                if self._has_forename_contradiction(norm_name, profile):
                    continue

                # 3. String similarity scores
                scores = [
                    fuzz.ratio(norm_name, profile.normalized_name),
                    fuzz.token_sort_ratio(norm_name, profile.normalized_name),
                ]
                cleaned_raw = profile.raw_name.lower().replace("dr.", "").replace("dr", "").replace("prof.", "").replace("prof", "").strip()
                scores.append(fuzz.ratio(norm_name, cleaned_raw))
                scores.append(fuzz.token_sort_ratio(norm_name, cleaned_raw))

                for variant in profile.name_variants:
                    scores.append(fuzz.ratio(norm_name, variant.name_variant.lower()))
                    scores.append(fuzz.token_sort_ratio(norm_name, variant.name_variant.lower()))

                base_score = max(scores) / 100.0

                # Reject if sister institution contradiction (e.g. author at Lara or VITS Hyd)
                if inst_category == "SIBLING_VIGNAN":
                    # Distinct sibling college (Lara, VITS, VIIT, Nirula) is a mismatch for VFSTR faculty
                    base_score = max(0.0, base_score - 0.40)
                elif inst_category == "EXTERNAL":
                    if affiliations:
                        # Conflicting external institution evidence (e.g. Mother Teresa Women's University)
                        # Strictly cap at 0.75 to route to ambiguous review, never auto-attribute
                        base_score = min(0.75, base_score - 0.10)
                    else:
                        # No affiliation metadata present at all: name-only matches must never auto-attribute
                        base_score = min(0.85, base_score)
                elif inst_category == "VFSTR":
                    # Strong canonical university boost if base score is already plausible
                    if base_score >= 0.75:
                        base_score = min(1.0, base_score + 0.20)
                elif inst_category == "GENERIC_VIGNAN":
                    if base_score >= 0.80:
                        base_score = min(0.90, base_score + 0.05)

                # If forename tokens are abbreviated/initials (e.g. 'P. S. Prasad' missing full 'Siva'), cap at 0.85
                non_initial_tokens = set(t for t in re.findall(r'[a-z]+', norm_name) if len(t) > 1)
                prof_forenames = set(t for t in re.findall(r'[a-z]+', cleaned_raw) if len(t) > 2 and t not in ("prasad", "kumar", "reddy", "rao", "sharma", "singh"))
                if prof_forenames and not any(pf in non_initial_tokens for pf in prof_forenames):
                    base_score = min(0.85, base_score)

                if base_score > best_score:
                    best_score = base_score
                    best_match_profile = profile

            # Auto-Attribution (Only for verified IDs or exact 0.95+ match)
            if best_score >= self.AUTO_ATTRIBUTION_THRESHOLD and best_match_profile:
                existing = any(a.faculty_id == best_match_profile.id for a in pub.authors)
                if not existing:
                    pub_auth = PublicationAuthor(
                        id=uuid.uuid4(),
                        publication_id=pub.id,
                        faculty_id=best_match_profile.id,
                        author_position=author_data.get("position", 1),
                        author_name_raw=raw_name,
                        attribution_confidence=best_score,
                        attribution_method="author_id_verified" if is_id_matched else "exact_identity_match",
                        is_corresponding=False,
                    )
                    self.session.add(pub_auth)
                    pub.authors.append(pub_auth)
                    
                    prov = ProvenanceRecord(
                        entity_type="publication_author",
                        entity_id=pub_auth.id,
                        event_type="attributed",
                        source="system",
                        detail=f"Auto-attributed to {best_match_profile.normalized_name} (score: {best_score:.2f})",
                        agent_name="FacultyAttributionAgent"
                    )
                    self.session.add(prov)
                    
                    stats["attributions_created"] += 1
                    stats["high_confidence"] += 1
                    
            elif best_score >= self.AMBIGUOUS_THRESHOLD and best_match_profile:
                # CANDIDATE ISOLATION: Ambiguous candidates create ReviewTask ONLY, NEVER PublicationAuthor
                stmt = select(ReviewTask).where(
                    ReviewTask.task_type == "attribution_ambiguous",
                    ReviewTask.entity_id == pub.id,
                    ReviewTask.related_entity_id == best_match_profile.id
                )
                existing = await self.session.execute(stmt)
                if not existing.scalars().first():
                    task = ReviewTask(
                        task_type="attribution_ambiguous",
                        priority="medium",
                        entity_type="publication",
                        entity_id=pub.id,
                        related_entity_id=best_match_profile.id,
                        explanation=f"Candidate attribution for author '{raw_name}' (score: {best_score:.2f})",
                        evidence={
                            "raw_author_name": raw_name,
                            "affiliations": affiliations,
                            "matched_faculty": best_match_profile.normalized_name,
                            "institution_category": inst_category
                        },
                        agent_name="FacultyAttributionAgent"
                    )
                    self.session.add(task)
                    stats["ambiguous"] += 1

    async def compute_faculty_pub_match(self, profile: FacultyProfile, pub: Publication) -> tuple[float, str, str]:
        """
        Evaluate match score between a specific faculty profile and publication.
        Returns: (score, method, matched_candidate_name)
        """
        author_candidates = self._parse_author_candidates(pub)
        if not author_candidates:
            return (0.0, "no_authors_found", "")

        best_score = 0.0
        best_method = "no_match"
        best_candidate_name = ""

        for author_data in author_candidates:
            raw_name = author_data.get("name", "")
            if not raw_name:
                continue

            norm_name = raw_name.lower().strip()
            affiliations = author_data.get("affiliations", []) or []
            if pub.affiliation_text and not affiliations:
                affiliations = [pub.affiliation_text]

            inst_category = self._classify_institution_affinity(affiliations)

            # 1. External Author Identifier match
            c_orcid = author_data.get("orcid") or ""
            c_oa_id = author_data.get("openalex_id") or ""
            for ident in profile.identifiers:
                if ident.identifier_type == "orcid" and ident.identifier_value and c_orcid:
                    if ident.identifier_value.lower() in c_orcid.lower():
                        return (1.0, "author_id_verified", raw_name)
                if ident.identifier_type == "openalex" and ident.identifier_value and c_oa_id:
                    if ident.identifier_value.lower() in c_oa_id.lower():
                        return (1.0, "author_id_verified", raw_name)

            # 2. Forename contradiction check (e.g. 'Sai' vs 'Siva')
            if self._has_forename_contradiction(norm_name, profile):
                continue

            # 3. String similarity scores
            scores = [
                fuzz.ratio(norm_name, profile.normalized_name),
                fuzz.token_sort_ratio(norm_name, profile.normalized_name),
            ]
            cleaned_raw = profile.raw_name.lower().replace("dr.", "").replace("dr", "").replace("prof.", "").replace("prof", "").strip()
            scores.append(fuzz.ratio(norm_name, cleaned_raw))
            scores.append(fuzz.token_sort_ratio(norm_name, cleaned_raw))

            for variant in profile.name_variants:
                scores.append(fuzz.ratio(norm_name, variant.name_variant.lower()))
                scores.append(fuzz.token_sort_ratio(norm_name, variant.name_variant.lower()))

            base_score = max(scores) / 100.0

            # Adjust for institution affinity
            if inst_category == "SIBLING_VIGNAN":
                base_score = max(0.0, base_score - 0.40)
            elif inst_category == "VFSTR":
                if base_score >= 0.75:
                    base_score = min(1.0, base_score + 0.20)
            elif inst_category == "GENERIC_VIGNAN":
                if base_score >= 0.80:
                    base_score = min(0.90, base_score + 0.05)

            # If forename tokens are abbreviated/initials, cap at 0.85
            non_initial_tokens = set(t for t in re.findall(r'[a-z]+', norm_name) if len(t) > 1)
            prof_forenames = set(t for t in re.findall(r'[a-z]+', cleaned_raw) if len(t) > 2 and t not in ("prasad", "kumar", "reddy", "rao", "sharma", "singh"))
            if prof_forenames and not any(pf in non_initial_tokens for pf in prof_forenames):
                base_score = min(0.85, base_score)

            if base_score > best_score:
                best_score = base_score
                best_candidate_name = raw_name
                if base_score >= self.AUTO_ATTRIBUTION_THRESHOLD:
                    best_method = "exact_identity_match"
                elif base_score >= self.AMBIGUOUS_THRESHOLD:
                    best_method = "ambiguous_candidate"
                else:
                    best_method = "low_confidence_match"

        return (best_score, best_method, best_candidate_name)
