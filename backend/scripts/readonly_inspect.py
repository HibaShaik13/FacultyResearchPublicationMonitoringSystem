import asyncio
import json
import sys
from uuid import UUID
import httpx
from sqlalchemy import select
from sqlalchemy.orm import selectinload

# Force utf-8 stdout
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from app.database import async_session_factory
from app.models.faculty import FacultyProfile
from app.models.publication import Publication, PublicationAuthor
from app.models.metrics import FacultyMetricSnapshot
from app.main import app

TARGET_FACULTY = [
    ("Dr Prashant Upadhyay", "3b04b44a-1add-48d5-a7bf-93c85164bb78"),
    ("Dr M Umadevi", "b836df5d-0fbe-4fa0-b977-7b185969f2b8"),
    ("Dr Venkatrama Phani Kumar S", "754179a9-ceef-4a60-8a9c-94e31d2fe1b8"),
]

async def read_only_inspection():
    report = {}

    # 1. Direct DB Query for Stored Database Records
    async with async_session_factory() as session:
        for name, fid_str in TARGET_FACULTY:
            fid = UUID(fid_str)
            stmt = (
                select(FacultyProfile)
                .options(
                    selectinload(FacultyProfile.metric_snapshots),
                    selectinload(FacultyProfile.publication_links).selectinload(PublicationAuthor.publication),
                )
                .where(FacultyProfile.id == fid)
            )
            res = await session.execute(stmt)
            fac = res.scalars().first()

            if not fac:
                report[name] = {"found": False}
                continue

            # Latest snapshot directly from DB table 'faculty_metric_snapshots'
            snap_stmt = (
                select(FacultyMetricSnapshot)
                .where(FacultyMetricSnapshot.faculty_id == fid)
                .order_by(FacultyMetricSnapshot.snapshot_date.desc())
            )
            snaps = (await session.execute(snap_stmt)).scalars().all()
            latest_snap = snaps[0] if snaps else None

            # Attributed publications
            pubs_sample = []
            for link in fac.publication_links[:8]:
                pub = link.publication
                if pub:
                    pubs_sample.append({
                        "title": pub.title,
                        "doi": pub.doi or "None",
                        "citation_count": pub.citation_count,
                        "citation_source": pub.citation_source or "none"
                    })

            report[name] = {
                "faculty_id": fid_str,
                "raw_name": fac.raw_name,
                "department": fac.department,
                "total_snapshots_in_db": len(snaps),
                "latest_snapshot_in_db": {
                    "snapshot_date": str(latest_snap.snapshot_date) if latest_snap else None,
                    "total_publications": latest_snap.total_publications if latest_snap else None,
                    "total_citations": latest_snap.total_citations if latest_snap else None,
                    "h_index": latest_snap.h_index if latest_snap else None,
                    "i10_index": latest_snap.i10_index if latest_snap else None,
                } if latest_snap else None,
                "attributed_publications_count": len(fac.publication_links),
                "sample_publications": pubs_sample
            }

    # 2. REST API Responses for consistency check
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for name, fid_str in TARGET_FACULTY:
            fac_resp = await client.get(f"/api/v1/faculty/{fid_str}")
            dash_resp = await client.get(f"/api/v1/analytics/dashboard?faculty_id={fid_str}")

            fac_data = fac_resp.json()
            dash_data = dash_resp.json()

            # Latest snapshot from faculty API
            fac_snaps = fac_data.get("metric_snapshots", [])
            latest_fac_snap = fac_snaps[-1] if fac_snaps else {}

            report[name]["api_verification"] = {
                "faculty_endpoint": {
                    "status_code": fac_resp.status_code,
                    "total_publications": latest_fac_snap.get("total_publications"),
                    "total_citations": latest_fac_snap.get("total_citations"),
                    "h_index": latest_fac_snap.get("h_index"),
                    "i10_index": latest_fac_snap.get("i10_index"),
                    "snapshot_date": latest_fac_snap.get("snapshot_date")
                },
                "dashboard_endpoint": {
                    "status_code": dash_resp.status_code,
                    "total_publications": dash_data.get("total_publications"),
                    "total_citations": dash_data.get("total_citations"),
                    "h_index": dash_data.get("h_index"),
                    "i10_index": dash_data.get("i10_index")
                },
                "metrics_consistent": (
                    latest_fac_snap.get("total_publications") == dash_data.get("total_publications") and
                    latest_fac_snap.get("total_citations") == dash_data.get("total_citations") and
                    latest_fac_snap.get("h_index") == dash_data.get("h_index") and
                    latest_fac_snap.get("i10_index") == dash_data.get("i10_index")
                )
            }

    with open("readonly_inspection_results.json", "w", encoding="utf-8") as out_f:
        json.dump(report, out_f, indent=2, default=str)
    
    print("READONLY_INSPECTION_COMPLETED_SUCCESSFULLY")

if __name__ == "__main__":
    asyncio.run(read_only_inspection())
