import logging
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.publication import Publication
from app.models.review import ReviewTask
from app.models.provenance import ProvenanceRecord
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class VerificationAgent:
    """Agent 10 - Verification & Evidence Agent"""
    
    def __init__(self, session: AsyncSession):
        self.session = session

    async def run(self) -> Dict[str, Any]:
        logger.info("Starting Verification Agent (Phase 10 - Agent 10)")
        
        # Load publications with their sources and authors
        stmt = select(Publication).options(
            selectinload(Publication.sources),
            selectinload(Publication.authors)
        )
        result = await self.session.execute(stmt)
        publications = result.scalars().unique().all()
        
        stats = {
            "processed": 0,
            "verified": 0,
            "partially_verified": 0,
            "needs_review": 0,
            "rejected": 0,
            "review_tasks": 0,
            "evidence_records": 0,
            "errors": 0
        }
        
        for pub in publications:
            stats["processed"] += 1
            try:
                await self._verify_publication(pub, stats)
            except Exception as e:
                logger.error(f"Error verifying publication {pub.id}: {e}")
                stats["errors"] += 1
                
        await self.session.commit()
        return stats

    async def _verify_publication(self, pub: Publication, stats: Dict[str, Any]):
        evidence = []
        score = 0.0
        
        # 1. DOI Evidence
        if pub.doi:
            if not pub.doi.startswith("10.") or " " in pub.doi:
                evidence.append("Invalid DOI format.")
                score -= 20
            else:
                evidence.append("Valid DOI present.")
                score += 30
        else:
            evidence.append("Missing DOI.")
            score -= 10
            
        # 2. Source Reliability & Metadata Consistency
        source_systems = [s.source_system for s in pub.sources]
        if len(source_systems) > 1:
            evidence.append(f"Multiple sources found ({', '.join(source_systems)}), indicating strong metadata consistency.")
            score += 30
        elif len(source_systems) == 1:
            evidence.append(f"Single source found ({source_systems[0]}).")
            score += 10
        else:
            evidence.append("No source metadata found.")
            score -= 20
            
        # 3. Authorship / Affiliation Evidence
        linked_faculty = [a for a in pub.authors if a.faculty_id is not None]
        if linked_faculty:
            best_confidence = max([a.attribution_confidence or 0.0 for a in linked_faculty])
            if best_confidence >= 0.85:
                evidence.append(f"High-confidence faculty attribution ({best_confidence:.2f}).")
                score += 40
            else:
                evidence.append(f"Low-confidence faculty attribution ({best_confidence:.2f}).")
                score += 10
        else:
            evidence.append("No faculty attribution found.")
            score -= 30
            
        # 4. Integrity / Risk Findings
        if pub.risk_level == "high":
            evidence.append("High integrity risk flagged.")
            score -= 50
        elif pub.risk_level == "medium":
            evidence.append("Medium integrity risk flagged.")
            score -= 20
        elif pub.risk_level == "low":
            evidence.append("Low integrity risk flagged.")
            score -= 5
        else:
            evidence.append("No integrity risks detected.")
            score += 10
            
        # Determine status
        score = max(0.0, min(100.0, score + 10))  # Base offset to keep it 0-100 logically
        status = "pending"
        
        if score >= 90 and pub.risk_level != "high" and pub.risk_level != "medium":
            status = "verified"
        elif score >= 60 and pub.risk_level != "high":
            status = "partially_verified"
        elif score < 30 or pub.risk_level == "high":
            status = "rejected"
        else:
            status = "needs_review"
            
        # If no sources at all, it's rejected or needs_review
        if not source_systems:
            status = "rejected"
            
        # Preserve human decisions
        if pub.verification_status in ["human_verified", "human_rejected", "human_corrected"]:
            return

        # Check idempotency
        if pub.verification_status == status and pub.metadata_confidence == score:
            return  # No change
            
        pub.verification_status = status
        pub.metadata_confidence = score
        pub.last_verified_at = datetime.now(timezone.utc)
        
        stats[status] += 1
        
        # Provenance Evidence Chain
        prov = ProvenanceRecord(
            entity_type="publication",
            entity_id=pub.id,
            event_type="verification_assessed",
            source="system",
            confidence=score,
            detail=f"Verification state '{status}'. Evidence chain: {' | '.join(evidence)}",
            agent_name="VerificationAgent"
        )
        self.session.add(prov)
        stats["evidence_records"] += 1
        
        # If unresolved contradiction or requires review -> ReviewTask
        if status in ["needs_review", "rejected"]:
            stmt = select(ReviewTask).where(
                ReviewTask.task_type == "verification_review",
                ReviewTask.entity_id == pub.id
            )
            existing = await self.session.execute(stmt)
            if not existing.scalars().first():
                task = ReviewTask(
                    task_type="verification_review",
                    priority="high" if status == "rejected" else "medium",
                    entity_type="publication",
                    entity_id=pub.id,
                    explanation=f"Publication requires human review. State: {status}, Score: {score:.1f}",
                    evidence={"evidence_chain": evidence, "score": score},
                    agent_name="VerificationAgent"
                )
                self.session.add(task)
                stats["review_tasks"] += 1
