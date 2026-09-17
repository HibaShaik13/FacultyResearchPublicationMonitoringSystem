"""
Comprehensive deep production data audit script.
Gathers ground-truth data for UNIFIED_IDENTITY_AUDIT.md.
"""

import asyncio
import json
import uuid
import sys
from pathlib import Path
from typing import Dict, Any, List
from datetime import date

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import selectinload

from app.database import async_session_factory
from app.models.faculty import FacultyProfile, FacultyIdentifier, FacultyNameVariant
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.review import ReviewTask
from app.models.metrics import FacultyMetricSnapshot, CitationSnapshot
from app.models.provenance import ProvenanceRecord
from app.config import get_settings


async def run_deep_audit() -> Dict[str, Any]:
    audit_data = {}
    async with async_session_factory() as session:
        settings = get_settings()

        # 1. Faculty Profiles and External Identifiers
        f_stmt = select(FacultyProfile).options(
            selectinload(FacultyProfile.name_variants),
            selectinload(FacultyProfile.identifiers),
            selectinload(FacultyProfile.publication_links).selectinload(PublicationAuthor.publication).selectinload(Publication.sources)
        ).where(FacultyProfile.status == "active")
        profiles = (await session.execute(f_stmt)).scalars().unique().all()

        faculty_list = []
        for p in profiles:
            ext_ids = {}
            for ident in p.identifiers:
                ext_ids[ident.identifier_type] = {
                    "value": ident.identifier_value,
                    "verified": ident.verified,
                    "confidence": ident.confidence,
                    "verification_source": ident.verification_source,
                    "created_at": ident.created_at.isoformat() if ident.created_at else None
                }

            confirmed_authors = [l for l in p.publication_links if l.publication]
            confirmed_pubs = [l.publication for l in confirmed_authors]

            # Review tasks for this faculty
            rt_stmt = select(ReviewTask).where(ReviewTask.related_entity_id == p.id)
            tasks = (await session.execute(rt_stmt)).scalars().all()
            pending_tasks = [t for t in tasks if t.status == "pending"]
            approved_tasks = [t for t in tasks if t.status == "approved"]
            rejected_tasks = [t for t in tasks if t.status == "rejected"]

            # Citation sources
            sources = set()
            for cp in confirmed_pubs:
                for s in (cp.sources or []):
                    sources.add(s.source_system)

            # Recompute metrics directly from confirmed pubs
            citations = [cp.citation_count or 0 for cp in confirmed_pubs]
            citations.sort(reverse=True)
            recomputed_h = 0
            for i, c in enumerate(citations):
                if c >= i + 1:
                    recomputed_h = i + 1
                else:
                    break
            recomputed_i10 = sum(1 for c in citations if c >= 10)
            recomputed_cits = sum(citations)
            recomputed_pubs = len(confirmed_pubs)

            # Compare with DB snapshot
            snap_stmt = select(FacultyMetricSnapshot).where(
                FacultyMetricSnapshot.faculty_id == p.id
            ).order_by(FacultyMetricSnapshot.snapshot_date.desc()).limit(1)
            snap = (await session.execute(snap_stmt)).scalars().first()

            snap_data = {
                "total_publications": snap.total_publications if snap else None,
                "total_citations": snap.total_citations if snap else None,
                "h_index": snap.h_index if snap else None,
                "i10_index": snap.i10_index if snap else None,
                "snapshot_date": snap.snapshot_date.isoformat() if snap and snap.snapshot_date else None
            }

            mismatch = False
            if snap:
                if (snap.total_publications != recomputed_pubs or 
                    snap.total_citations != recomputed_cits or 
                    snap.h_index != recomputed_h or 
                    snap.i10_index != recomputed_i10):
                    mismatch = True

            faculty_list.append({
                "faculty_id": str(p.id),
                "name": p.raw_name,
                "normalized_name": p.normalized_name,
                "department": p.department,
                "designation": p.designation,
                "email": p.institutional_email or p.raw_email,
                "name_variants": [nv.name_variant for nv in p.name_variants],
                "identifiers": ext_ids,
                "confirmed_publications_count": recomputed_pubs,
                "confirmed_citations_sum": recomputed_cits,
                "recomputed_h_index": recomputed_h,
                "recomputed_i10_index": recomputed_i10,
                "db_snapshot": snap_data,
                "metric_mismatch": mismatch,
                "pending_reviews_count": len(pending_tasks),
                "approved_reviews_count": len(approved_tasks),
                "rejected_reviews_count": len(rejected_tasks),
                "citation_sources": list(sources)
            })

        audit_data["faculty_profiles"] = faculty_list

        # 2. Dr. M. Umadevi Detailed Reference Audit
        uma_profile = next((p for p in profiles if "umadevi" in p.normalized_name), None)
        if uma_profile:
            uma_confirmed = [l.publication for l in uma_profile.publication_links if l.publication]
            uma_pubs_list = []
            for cp in uma_confirmed:
                uma_pubs_list.append({
                    "id": str(cp.id),
                    "title": cp.title,
                    "doi": cp.doi,
                    "year": cp.year,
                    "citation_count": cp.citation_count,
                    "verification_status": cp.verification_status,
                    "sources": [
                        {
                            "system": s.source_system,
                            "source_id": s.source_id,
                            "url": s.source_url,
                            "method": s.discovery_method
                        }
                        for s in (cp.sources or [])
                    ]
                })

            rt_stmt = select(ReviewTask).where(ReviewTask.related_entity_id == uma_profile.id)
            uma_tasks = (await session.execute(rt_stmt)).scalars().all()

            audit_data["dr_umadevi_reference"] = {
                "faculty_id": str(uma_profile.id),
                "name": uma_profile.raw_name,
                "identifiers": {i.identifier_type: i.identifier_value for i in uma_profile.identifiers},
                "confirmed_publications": uma_pubs_list,
                "pending_tasks_count": len([t for t in uma_tasks if t.status == "pending"]),
                "rejected_tasks_count": len([t for t in uma_tasks if t.status == "rejected"])
            }

        # 3. Data Integrity & Orphan Audits
        # Duplicate DOIs
        doi_dups_stmt = select(Publication.doi, func.count(Publication.id)).where(Publication.doi.isnot(None)).group_by(Publication.doi).having(func.count(Publication.id) > 1)
        doi_dups = (await session.execute(doi_dups_stmt)).all()

        # Orphan PublicationAuthors
        orphan_pa_stmt = select(func.count(PublicationAuthor.id)).where(
            or_(
                ~PublicationAuthor.faculty_id.in_(select(FacultyProfile.id)),
                ~PublicationAuthor.publication_id.in_(select(Publication.id))
            )
        )
        orphan_pa = (await session.execute(orphan_pa_stmt)).scalar() or 0

        # Orphan PublicationSources
        orphan_ps_stmt = select(func.count(PublicationSource.id)).where(
            ~PublicationSource.publication_id.in_(select(Publication.id))
        )
        orphan_ps = (await session.execute(orphan_ps_stmt)).scalar() or 0

        # Orphan ReviewTasks
        orphan_rt_stmt = select(func.count(ReviewTask.id)).where(
            and_(
                ReviewTask.entity_type == "publication",
                ~ReviewTask.entity_id.in_(select(Publication.id))
            )
        )
        orphan_rt = (await session.execute(orphan_rt_stmt)).scalar() or 0

        # Canonical multi-source publications count
        multi_src_stmt = select(func.count(Publication.id)).where(
            Publication.id.in_(
                select(PublicationSource.publication_id).group_by(PublicationSource.publication_id).having(func.count(PublicationSource.id) > 1)
            )
        )
        multi_source_pubs_count = (await session.execute(multi_src_stmt)).scalar() or 0

        total_pubs = (await session.execute(select(func.count(Publication.id)))).scalar() or 0
        total_sources = (await session.execute(select(func.count(PublicationSource.id)))).scalar() or 0
        total_authors = (await session.execute(select(func.count(PublicationAuthor.id)))).scalar() or 0
        total_tasks = (await session.execute(select(func.count(ReviewTask.id)))).scalar() or 0

        audit_data["integrity"] = {
            "duplicate_dois_count": len(doi_dups),
            "duplicate_dois": [d[0] for d in doi_dups],
            "orphan_publication_authors": orphan_pa,
            "orphan_publication_sources": orphan_ps,
            "orphan_review_tasks": orphan_rt,
            "total_canonical_publications": total_pubs,
            "total_publication_sources": total_sources,
            "total_publication_authors": total_authors,
            "total_review_tasks": total_tasks,
            "multi_source_deduplicated_publications": multi_source_pubs_count
        }

        # 4. Credential & API Status
        audit_data["api_status"] = {
            "ieee": {
                "configured": bool(settings.ieee_api_key),
                "status": "CONFIGURED" if settings.ieee_api_key else "ACCESS_UNAVAILABLE"
            },
            "scopus": {
                "configured": bool(settings.scopus_api_key),
                "status": "CONFIGURED" if settings.scopus_api_key else "ACCESS_UNAVAILABLE"
            },
            "openalex": {
                "configured": True,
                "status": "CONFIGURED (POLITE POOL)"
            },
            "crossref": {
                "configured": True,
                "status": "CONFIGURED (POLITE POOL)"
            },
            "orcid": {
                "configured": bool(settings.orcid_client_id),
                "status": "CONFIGURED" if settings.orcid_client_id else "ACCESS_UNAVAILABLE"
            },
            "semantic_scholar": {
                "configured": bool(settings.semantic_scholar_api_key),
                "status": "CONFIGURED" if settings.semantic_scholar_api_key else "PUBLIC_RATE_LIMITED"
            }
        }

    return audit_data


if __name__ == "__main__":
    res = asyncio.run(run_deep_audit())
    with open("deep_audit_results.json", "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print("Audit completed successfully. Results saved to deep_audit_results.json")
