import logging
import re
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from rapidfuzz import fuzz

from app.models.publication import Publication
from app.models.review import ReviewTask
from app.models.provenance import ProvenanceRecord
from app.data.predatory_indicators import check_predatory_indicators, RAPID_PUBLICATION_THRESHOLD_DAYS

logger = logging.getLogger(__name__)

class ResearchIntegrityAgent:
    """Agent 8 - Research Integrity / Risk Agent"""
    
    def __init__(self, session: AsyncSession):
        self.session = session

    async def run(self) -> Dict[str, Any]:
        logger.info("Starting Research Integrity Agent (Phase 8 - Agent 8)")
        
        stmt = select(Publication).options(
            selectinload(Publication.sources)
        )
        result = await self.session.execute(stmt)
        publications = result.scalars().unique().all()
        
        stats = {
            "processed": 0,
            "low": 0,
            "medium": 0,
            "high": 0,
            "review_required": 0,
            "issues_detected": 0,
            "predatory_flagged": 0,
            "rapid_publication_flagged": 0,
            "errors": 0
        }
        
        for pub in publications:
            stats["processed"] += 1
            try:
                await self._evaluate_integrity(pub, stats)
            except Exception as e:
                logger.error(f"Error evaluating integrity for publication {pub.id}: {e}")
                stats["errors"] += 1
                
        await self.session.commit()
        return stats

    def _extract_title_from_source(self, raw: dict, system: str) -> str:
        if system == "crossref":
            titles = raw.get("title", [])
            return titles[0] if titles else ""
        elif system == "openalex":
            return raw.get("title", "")
        return ""

    def _extract_year_from_source(self, raw: dict, system: str) -> int:
        if system == "crossref":
            try:
                # Crossref date-parts
                date_parts = raw.get("published", {}).get("date-parts", [[]])
                if date_parts and date_parts[0]:
                    return int(date_parts[0][0])
            except Exception:
                pass
        elif system == "openalex":
            try:
                return int(raw.get("publication_year", 0))
            except Exception:
                pass
        return 0

    async def _evaluate_integrity(self, pub: Publication, stats: Dict[str, Any]):
        reasons = {}
        risk_score = 0  # 1 = low, 2 = medium, 3 = high
        
        # 1. Invalid DOI check
        if pub.doi:
            if not pub.doi.startswith("10.") or " " in pub.doi:
                reasons["invalid_doi"] = f"DOI format appears invalid: '{pub.doi}'"
                risk_score = max(risk_score, 2)
        else:
            reasons["missing_doi"] = "Publication lacks a DOI"
            risk_score = max(risk_score, 1)
            
        # Compare sources if we have multiple
        if len(pub.sources) > 1:
            titles = []
            years = []
            
            for source in pub.sources:
                if not source.raw_metadata: continue
                t = self._extract_title_from_source(source.raw_metadata, source.source_system)
                if t: titles.append((t, source.source_system))
                
                y = self._extract_year_from_source(source.raw_metadata, source.source_system)
                if y: years.append((y, source.source_system))
                
            # Check title conflicts
            if len(titles) >= 2:
                for i in range(len(titles)):
                    for j in range(i + 1, len(titles)):
                        t1, s1 = titles[i]
                        t2, s2 = titles[j]
                        if fuzz.ratio(t1.lower(), t2.lower()) < 60:
                            reasons["title_conflict"] = f"Title mismatch between {s1} and {s2}"
                            risk_score = max(risk_score, 3)
                            
            # Check year conflicts
            if len(years) >= 2:
                year_vals = list(set([y for y, s in years]))
                if len(year_vals) > 1:
                    diff = max(year_vals) - min(year_vals)
                    if diff > 1:
                        reasons["year_conflict"] = f"Publication year varies by {diff} years across sources."
                        risk_score = max(risk_score, 2)

        # 3. Predatory journal / publisher detection
        predatory_check = check_predatory_indicators(
            journal_name=pub.journal_name or "",
            publisher=pub.publisher or ""
        )
        if predatory_check["is_suspicious"]:
            reasons["predatory_indicator"] = predatory_check["reasons"][0] if predatory_check["reasons"] else "Predatory indicator detected"
            reasons["predatory_category"] = predatory_check["risk_category"]
            risk_score = max(risk_score, 3)  # Always high risk
            stats["predatory_flagged"] += 1

        # 4. Rapid publication detection
        # Check raw metadata from sources for submission/acceptance dates
        for source in pub.sources:
            if not source.raw_metadata:
                continue
            raw = source.raw_metadata
            # Crossref may contain 'created' and 'deposited' dates
            if source.source_system == "crossref":
                try:
                    created_parts = raw.get("created", {}).get("date-parts", [[]])
                    published_parts = raw.get("published", {}).get("date-parts", [[]])
                    if created_parts and created_parts[0] and published_parts and published_parts[0]:
                        from datetime import date
                        created_date = date(created_parts[0][0], created_parts[0][1] if len(created_parts[0]) > 1 else 1, created_parts[0][2] if len(created_parts[0]) > 2 else 1)
                        pub_date = date(published_parts[0][0], published_parts[0][1] if len(published_parts[0]) > 1 else 1, published_parts[0][2] if len(published_parts[0]) > 2 else 1)
                        delta = (pub_date - created_date).days
                        if 0 < delta < RAPID_PUBLICATION_THRESHOLD_DAYS:
                            reasons["rapid_publication"] = f"Publication appeared within {delta} days of deposit (threshold: {RAPID_PUBLICATION_THRESHOLD_DAYS} days)"
                            risk_score = max(risk_score, 2)
                            stats["rapid_publication_flagged"] += 1
                except Exception:
                    pass  # Date parsing errors are non-fatal
                        
        # Save results if changed (idempotency: only save if reasons are different)
        existing_reasons = pub.risk_reasons or {}
        if existing_reasons != reasons:
            pub.risk_reasons = reasons
            
            if risk_score == 0:
                pub.risk_level = "none"
            elif risk_score == 1:
                pub.risk_level = "low"
            elif risk_score == 2:
                pub.risk_level = "medium"
            elif risk_score >= 3:
                pub.risk_level = "high"
                
            if risk_score > 0:
                stats["issues_detected"] += len(reasons)
                
                # Provenance
                prov = ProvenanceRecord(
                    entity_type="publication",
                    entity_id=pub.id,
                    event_type="risk_assessed",
                    source="system",
                    detail=f"Assessed risk as {pub.risk_level} with reasons: {list(reasons.keys())}",
                    agent_name="ResearchIntegrityAgent"
                )
                self.session.add(prov)
                
            # If high risk, create ReviewTask
            if risk_score >= 3:
                stmt = select(ReviewTask).where(
                    ReviewTask.task_type == "risk_flag",
                    ReviewTask.entity_id == pub.id
                )
                existing = await self.session.execute(stmt)
                if not existing.scalars().first():
                    task = ReviewTask(
                        task_type="risk_flag",
                        priority="high",
                        entity_type="publication",
                        entity_id=pub.id,
                        explanation=f"High risk integrity issues detected: {', '.join(reasons.keys())}",
                        evidence=reasons,
                        agent_name="ResearchIntegrityAgent"
                    )
                    self.session.add(task)
                    stats["review_required"] += 1
                    
        # Tally stats based on current pub state
        if pub.risk_level == "low": stats["low"] += 1
        elif pub.risk_level == "medium": stats["medium"] += 1
        elif pub.risk_level == "high": stats["high"] += 1
