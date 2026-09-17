import asyncio
import json
import sys
import re
from uuid import UUID
from datetime import datetime
import httpx
from sqlalchemy import select, func, distinct
from sqlalchemy.orm import selectinload

# Force utf-8 stdout
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from app.config import get_settings
from app.database import async_session_factory
from app.models.faculty import FacultyProfile, FacultyIdentifier, FacultyNameVariant
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.metrics import FacultyMetricSnapshot, CitationSnapshot
from app.scheduler import start_scheduler, stop_scheduler, get_scheduler_status
from app.main import app

def mask_url(url: str) -> str:
    return re.sub(r':([^@]+)@', ':***@', url)

async def audit():
    settings = get_settings()
    audit_data = {}
    
    # 1. Database Environment Info
    raw_db_url = settings.database_url
    masked_db = mask_url(raw_db_url)
    audit_data["database_environment"] = {
        "url_masked": masked_db,
        "is_asyncpg": "asyncpg" in raw_db_url,
        "environment": settings.app_env,
        "is_production": (settings.app_env == "production")
    }

    # 2. Inspect Target Faculty:
    # Dr. Prashant Upadhyay, Dr. M. Umadevi, Dr. Venkatrama Phani Kumar S, Dr. K.V. Krishna Kishore
    target_names = ["prashant upadhyay", "m umadevi", "venkatrama phani kumar s", "krishna kishore", "s n tirumala rao"]
    target_results = {}
    
    async with async_session_factory() as session:
        for tname in target_names:
            stmt = select(FacultyProfile).options(
                selectinload(FacultyProfile.publication_links).selectinload(PublicationAuthor.publication),
                selectinload(FacultyProfile.metric_snapshots),
                selectinload(FacultyProfile.identifiers),
                selectinload(FacultyProfile.name_variants),
            ).where(FacultyProfile.normalized_name.ilike(f"%{tname}%"))
            
            res = await session.execute(stmt)
            fac = res.scalars().first()
            if not fac:
                target_results[tname] = {"found": False, "note": "Not present in seeded faculty_profiles_cse.csv dataset"}
                continue

            links = fac.publication_links
            link_count = len(links)
            unique_pub_ids = set(l.publication_id for l in links if l.publication_id)
            unique_pub_count = len(unique_pub_ids)
            
            # Citations list
            citations = []
            citation_sources = set()
            for l in links:
                pub = l.publication
                if pub:
                    citations.append(pub.citation_count or 0)
                    if pub.citation_source:
                        citation_sources.add(pub.citation_source)
            
            citations_sorted = sorted(citations, reverse=True)
            total_citations = sum(citations)
            
            # Calculate h-index
            h = 0
            for i, c in enumerate(citations_sorted, 1):
                if c >= i:
                    h = i
                else:
                    break
            
            # Calculate i10-index
            i10 = sum(1 for c in citations if c >= 10)
            
            # Latest snapshot
            latest_snap = None
            if fac.metric_snapshots:
                latest_snap = sorted(fac.metric_snapshots, key=lambda s: s.snapshot_date)[-1]

            target_results[fac.raw_name] = {
                "faculty_id": str(fac.id),
                "raw_name": fac.raw_name,
                "department": fac.department,
                "declared_publication_count": fac.declared_publication_count,
                "unique_attributed_publication_count": unique_pub_count,
                "publication_author_link_count": link_count,
                "total_citations": total_citations,
                "h_index": h,
                "i10_index": i10,
                "citation_sources_used": list(citation_sources),
                "sorted_citations_sample": citations_sorted[:20],
                "latest_snapshot": {
                    "snapshot_date": str(latest_snap.snapshot_date) if latest_snap else None,
                    "total_publications": latest_snap.total_publications if latest_snap else None,
                    "total_citations": latest_snap.total_citations if latest_snap else None,
                    "h_index": latest_snap.h_index if latest_snap else None,
                    "i10_index": latest_snap.i10_index if latest_snap else None,
                } if latest_snap else None
            }

        # 3. Verify deduplication and PublicationAuthor validity
        total_pub_authors = (await session.execute(select(func.count(PublicationAuthor.id)))).scalar()
        valid_pub_authors = (await session.execute(
            select(func.count(PublicationAuthor.id))
            .where(PublicationAuthor.faculty_id.isnot(None))
            .where(PublicationAuthor.publication_id.isnot(None))
        )).scalar()
        
        audit_data["attribution_integrity"] = {
            "total_publication_authors": total_pub_authors,
            "valid_foreign_keys": valid_pub_authors,
            "foreign_key_validity_percent": (valid_pub_authors / total_pub_authors * 100) if total_pub_authors else 100
        }

    audit_data["faculty_profiles"] = target_results

    # 4. API Endpoints Testing via ASGI Client
    from app.core.security import create_access_token
    admin_token = create_access_token(data={"sub": "admin@vignan.ac.in", "role": "research_admin"})
    auth_headers = {"Authorization": f"Bearer {admin_token}"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # A. Publications Stats
        stats_resp = await client.get("/api/v1/publications/stats")
        audit_data["api_publications_stats"] = {
            "status_code": stats_resp.status_code,
            "data": stats_resp.json()
        }

        # B. Discovery Status & Runs (Authenticated)
        disc_status = await client.get("/api/v1/discovery/status", headers=auth_headers)
        disc_runs = await client.get("/api/v1/discovery/runs", headers=auth_headers)
        audit_data["api_discovery_status"] = {
            "status_code": disc_status.status_code,
            "system_health": disc_status.json().get("system_health")
        }
        audit_data["api_discovery_runs"] = {
            "status_code": disc_runs.status_code,
            "total_runs": len(disc_runs.json()) if isinstance(disc_runs.json(), list) else 0,
            "latest_run": disc_runs.json()[-1] if isinstance(disc_runs.json(), list) and len(disc_runs.json()) > 0 else None
        }

        # C. Test Faculty endpoints for Dr. Prashant Upadhyay
        first_fac = target_results.get("Dr Prashant Upadhyay")
        if first_fac and first_fac.get("faculty_id"):
            fid = first_fac["faculty_id"]
            f_resp = await client.get(f"/api/v1/faculty/{fid}")
            d_resp = await client.get(f"/api/v1/analytics/dashboard?faculty_id={fid}")
            p_resp = await client.get(f"/api/v1/publications/?faculty_id={fid}")
            audit_data["api_faculty_profile"] = {
                "status_code": f_resp.status_code,
                "name": f_resp.json().get("raw_name"),
                "snapshots_count": len(f_resp.json().get("metric_snapshots", []))
            }
            audit_data["api_analytics_dashboard"] = {
                "status_code": d_resp.status_code,
                "metrics": d_resp.json()
            }
            audit_data["api_faculty_publications"] = {
                "status_code": p_resp.status_code,
                "total": p_resp.json().get("total")
            }

        # D. Trigger discovery test (Authenticated)
        trig_resp = await client.post("/api/v1/discovery/trigger", headers=auth_headers)
        audit_data["api_discovery_trigger"] = {
            "status_code": trig_resp.status_code,
            "data": trig_resp.json()
        }

    # 5. Scheduler job configuration & lifecycle
    sched = start_scheduler()
    sched_status = get_scheduler_status()
    stop_scheduler()
    
    audit_data["scheduler_configuration"] = {
        "status": sched_status,
        "cron_settings": {
            "sync_full_discovery": settings.sync_full_discovery,
            "sync_citation_refresh": settings.sync_citation_refresh,
            "sync_metrics_compute": settings.sync_metrics_compute,
            "sync_alert_generation": settings.sync_alert_generation,
            "sync_report_generation": settings.sync_report_generation,
        }
    }

    with open("final_audit_results.json", "w", encoding="utf-8") as out_f:
        json.dump(audit_data, out_f, indent=2, default=str)
    
    print("FINAL_AUDIT_COMPLETED_SUCCESSFULLY")

if __name__ == "__main__":
    asyncio.run(audit())
