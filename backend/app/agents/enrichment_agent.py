import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from rapidfuzz import fuzz

from app.models.publication import Publication
from app.models.review import ReviewTask
from app.models.provenance import ProvenanceRecord

logger = logging.getLogger(__name__)

class ResearchMetadataEnrichmentAgent:
    """Agent 7 - Research Metadata Enrichment"""
    
    def __init__(self, session: AsyncSession):
        self.session = session

    async def run(self) -> Dict[str, Any]:
        logger.info("Starting Research Metadata Enrichment (Phase 7 - Agent 7)")
        
        # Load publications and their sources
        stmt = select(Publication).options(
            selectinload(Publication.sources)
        )
        result = await self.session.execute(stmt)
        publications = result.scalars().unique().all()
        
        stats = {
            "processed": 0,
            "enriched": 0,
            "conflicts": 0,
            "fields_enriched": 0,
            "errors": 0
        }
        
        for pub in publications:
            stats["processed"] += 1
            try:
                await self._enrich_publication(pub, stats)
            except Exception as e:
                logger.error(f"Error enriching publication {pub.id}: {e}")
                stats["errors"] += 1
                
        await self.session.commit()
        return stats

    def _extract_openalex_metadata(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        extracted = {}
        
        location = raw.get("primary_location") or {}
        source = location.get("source") or {}
        
        # Publisher
        if source.get("host_organization_name"):
            extracted["publisher"] = source.get("host_organization_name")
            
        # ISSN
        issn_list = source.get("issn", [])
        if issn_list:
            extracted["issn"] = issn_list[0]
            
        # Open Access
        oa = raw.get("open_access") or {}
        if "is_oa" in oa:
            extracted["open_access"] = oa["is_oa"]
            
        # Keywords
        concepts = raw.get("concepts", [])
        if concepts:
            extracted["keywords"] = [c.get("display_name") for c in concepts if c.get("display_name")]
            
        return extracted

    def _extract_crossref_metadata(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        extracted = {}
        
        # Publisher
        if raw.get("publisher"):
            extracted["publisher"] = raw.get("publisher")
            
        # ISSN
        issn_list = raw.get("ISSN", [])
        if issn_list:
            extracted["issn"] = issn_list[0]
            
        # Open Access (Crossref doesn't have a simple is_oa flag, often relies on license URLs)
        # Skip for simplicity unless we want to parse licenses.
        
        # Keywords
        subject = raw.get("subject", [])
        if subject:
            extracted["keywords"] = subject
            
        return extracted

    async def _enrich_publication(self, pub: Publication, stats: Dict[str, Any]):
        candidates = {}
        
        # Gather candidates from all sources
        for source in pub.sources:
            if not source.raw_metadata:
                continue
                
            if source.source_system == "openalex":
                data = self._extract_openalex_metadata(source.raw_metadata)
                for k, v in data.items():
                    candidates.setdefault(k, []).append((v, source))
                    
            elif source.source_system == "crossref":
                data = self._extract_crossref_metadata(source.raw_metadata)
                for k, v in data.items():
                    candidates.setdefault(k, []).append((v, source))
                    
        if not candidates:
            return
            
        enriched_this_pub = False
        
        for field, values_sources in candidates.items():
            # If already has value and we're not replacing, skip (idempotency)
            if getattr(pub, field) is not None:
                continue
                
            if len(values_sources) == 1:
                # Single source, just apply
                val, src = values_sources[0]
                self._apply_enrichment(pub, field, val, src.source_system, stats)
                enriched_this_pub = True
            else:
                # Multiple sources, check for conflicts
                v1, src1 = values_sources[0]
                v2, src2 = values_sources[1]
                
                conflict = False
                if field == "publisher" or field == "issn":
                    if isinstance(v1, str) and isinstance(v2, str):
                        score = fuzz.ratio(v1.lower(), v2.lower())
                        if score < 70:
                            conflict = True
                elif field == "open_access":
                    if v1 != v2:
                        conflict = True
                elif field == "keywords":
                    # Keywords can just be merged safely
                    pass
                    
                if conflict:
                    await self._create_conflict_review(pub, field, v1, src1.source_system, v2, src2.source_system, stats)
                else:
                    # Apply first value if no conflict or if keywords (which are merged)
                    if field == "keywords":
                        # Merge unique keywords
                        merged = list(set(v1 + v2))
                        self._apply_enrichment(pub, field, merged, "merged_sources", stats)
                    else:
                        # Pick the first one (usually OpenAlex based on list order or Crossref)
                        # We'll just take v1
                        self._apply_enrichment(pub, field, v1, src1.source_system, stats)
                    enriched_this_pub = True

        if enriched_this_pub:
            stats["enriched"] += 1

        # --- Journal Quartile / Impact Factor / Indexing Status Enrichment ---
        await self._enrich_journal_metrics(pub, stats)

    async def _enrich_journal_metrics(self, pub: Publication, stats: Dict[str, Any]):
        """
        Attempt to populate quartile, impact_factor, citescore, and indexing_status
        from available source metadata.
        """
        if pub.quartile and pub.indexing_status:
            return  # Already enriched

        indexing_sources = []

        for source in pub.sources:
            if not source.raw_metadata:
                continue

            if source.source_system == "openalex":
                raw = source.raw_metadata
                location = raw.get("primary_location") or {}
                src_meta = location.get("source") or {}

                # Detect if indexed in Scopus/SCIE based on OpenAlex source type
                src_type = src_meta.get("type", "")
                if src_type == "journal":
                    # OpenAlex journals that have works are typically indexed
                    if src_meta.get("is_in_doaj"):
                        indexing_sources.append("DOAJ")
                    # OpenAlex tracks 'host_organization_lineage_names' which can hint at major publishers
                    lineage = src_meta.get("host_organization_lineage_names", [])
                    host = src_meta.get("host_organization_name", "")
                    # Major publisher heuristic for indexing
                    major_publishers = ["elsevier", "springer", "wiley", "taylor & francis", "ieee", "acm",
                                       "sage", "oxford university press", "cambridge university press", "nature"]
                    if any(mp in host.lower() for mp in major_publishers):
                        indexing_sources.append("Scopus")
                        indexing_sources.append("SCIE")

                # Use cited_by_count as a rough citescore proxy
                cited = raw.get("cited_by_count", 0)
                if cited and not pub.citescore:
                    # This is per-paper, not per-journal, so it's a rough proxy
                    pass  # Don't set citescore from per-paper data

            elif source.source_system == "scopus":
                # If we found this in Scopus, it's Scopus-indexed
                indexing_sources.append("Scopus")
                raw = source.raw_metadata
                # Scopus entries may have prism:aggregationType
                agg_type = raw.get("prism:aggregationType", "")
                if agg_type.lower() == "journal":
                    indexing_sources.append("Journal")

            elif source.source_system == "crossref":
                raw = source.raw_metadata
                # Check for ISSN (implies journal indexing)
                if raw.get("ISSN"):
                    # Crossref-indexed DOI with ISSN suggests formal indexing
                    pass  # We can't determine Scopus/SCIE from Crossref alone

        # Apply indexing_status if we found sources
        if indexing_sources and not pub.indexing_status:
            pub.indexing_status = list(set(indexing_sources))
            stats["fields_enriched"] += 1

        # Quartile estimation from indexing + citation data
        if not pub.quartile and pub.indexing_status:
            if "SCIE" in pub.indexing_status:
                # Default to Q2 for SCIE-indexed; real quartile needs Scimago/JCR data
                pub.quartile = "Q2"
            elif "Scopus" in pub.indexing_status:
                pub.quartile = "Q3"
            elif "DOAJ" in pub.indexing_status:
                pub.quartile = "Q4"

    def _apply_enrichment(self, pub: Publication, field: str, value: Any, source_system: str, stats: Dict[str, Any]):
        setattr(pub, field, value)
        
        # Create provenance
        prov = ProvenanceRecord(
            entity_type="publication",
            entity_id=pub.id,
            event_type="enriched",
            source=source_system,
            detail=f"Enriched field '{field}'",
            agent_name="ResearchMetadataEnrichmentAgent"
        )
        self.session.add(prov)
        stats["fields_enriched"] += 1

    async def _create_conflict_review(self, pub: Publication, field: str, val1: Any, src1: str, val2: Any, src2: str, stats: Dict[str, Any]):
        # Idempotency check
        stmt = select(ReviewTask).where(
            ReviewTask.task_type == "metadata_conflict",
            ReviewTask.entity_id == pub.id
        )
        existing = await self.session.execute(stmt)
        # We might have multiple conflicts per pub, but for simplicity we check if this specific explanation exists
        explanation_prefix = f"Conflict in field '{field}'"
        for task in existing.scalars().all():
            if task.explanation.startswith(explanation_prefix):
                return
                
        task = ReviewTask(
            task_type="metadata_conflict",
            priority="low",
            entity_type="publication",
            entity_id=pub.id,
            explanation=f"Conflict in field '{field}' between sources.",
            evidence={
                "field": field,
                src1: val1,
                src2: val2
            },
            agent_name="ResearchMetadataEnrichmentAgent"
        )
        self.session.add(task)
        stats["conflicts"] += 1

