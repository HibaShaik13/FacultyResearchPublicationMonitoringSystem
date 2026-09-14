import logging
import uuid
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
            selectinload(Publication.authors)
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

    def _is_vignan_affiliation(self, affiliations: List[str]) -> bool:
        if not affiliations:
            return False
        for affil in affiliations:
            affil_lower = affil.lower()
            if any(v in affil_lower for v in self.affiliation_keywords):
                return True
        return False

    async def _process_publication(self, pub: Publication, stats: Dict[str, Any]):
        if not pub.authors_parsed:
            return

        for author_data in pub.authors_parsed:
            raw_name = author_data.get("name", "")
            if not raw_name:
                continue
                
            norm_name = raw_name.lower().strip()
            affiliations = author_data.get("affiliations", [])
            has_vignan_affil = self._is_vignan_affiliation(affiliations)
            
            best_match_profile = None
            best_score = 0.0
            
            for profile in self.faculty_cache:
                # Basic ratio
                scores = [fuzz.token_set_ratio(norm_name, profile.normalized_name)]
                for variant in profile.name_variants:
                    scores.append(fuzz.token_set_ratio(norm_name, variant.name_variant))
                    
                profile_score = max(scores) / 100.0
                
                # Boost if affiliation matches
                if profile_score > 0.6 and has_vignan_affil:
                    profile_score = min(1.0, profile_score + 0.15)
                    
                if profile_score > best_score:
                    best_score = profile_score
                    best_match_profile = profile

            # High confidence threshold
            if best_score > 0.85 and best_match_profile:
                # Check idempotency
                existing = any(a.faculty_id == best_match_profile.id for a in pub.authors)
                if not existing:
                    pub_auth = PublicationAuthor(
                        id=uuid.uuid4(),
                        publication_id=pub.id,
                        faculty_id=best_match_profile.id,
                        author_position=author_data.get("position"),
                        author_name_raw=raw_name,
                        attribution_confidence=best_score,
                        attribution_method="name_affiliation_heuristic"
                    )
                    self.session.add(pub_auth)
                    pub.authors.append(pub_auth)
                    
                    prov = ProvenanceRecord(
                        entity_type="publication_author",
                        entity_id=pub_auth.id,
                        event_type="attributed",
                        source="system",
                        detail=f"Attributed to {best_match_profile.normalized_name} (score: {best_score})",
                        agent_name="FacultyAttributionAgent"
                    )
                    self.session.add(prov)
                    
                    stats["attributions_created"] += 1
                    stats["high_confidence"] += 1
                    
            elif best_score > 0.70 and best_match_profile:
                # Ambiguous match, create review task
                # Check idempotency
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
                        explanation=f"Ambiguous attribution for author '{raw_name}' (score: {best_score})",
                        evidence={
                            "raw_author_name": raw_name,
                            "affiliations": affiliations,
                            "matched_faculty": best_match_profile.normalized_name
                        },
                        agent_name="FacultyAttributionAgent"
                    )
                    self.session.add(task)
                    stats["ambiguous"] += 1
