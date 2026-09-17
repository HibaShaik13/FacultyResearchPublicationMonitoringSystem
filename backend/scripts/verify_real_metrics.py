import asyncio
import json
import logging
import sys
from uuid import UUID
import httpx
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

# Force utf-8 stdout
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from app.database import async_session_factory
from app.models.faculty import FacultyProfile, FacultyIdentifier
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.metrics import FacultyMetricSnapshot, CitationSnapshot
from app.main import app

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("verify_metrics")

TARGET_FACULTY_ID = UUID("38e4c234-7d43-47af-8c08-980c6ca097ae")

async def run_verification():
    print("\n=======================================================")
    print("STEP 1: DATABASE METRICS & ATTRIBUTION INSPECTION")
    print("=======================================================")
    
    test_faculty_ids = [TARGET_FACULTY_ID]

    async with async_session_factory() as session:
        # Check target faculty
        res = await session.execute(
            select(FacultyProfile)
            .options(
                selectinload(FacultyProfile.identifiers),
                selectinload(FacultyProfile.name_variants),
                selectinload(FacultyProfile.publication_links).selectinload(PublicationAuthor.publication),
                selectinload(FacultyProfile.metric_snapshots),
            )
            .where(FacultyProfile.id == TARGET_FACULTY_ID)
        )
        target_fac = res.scalars().first()
        if not target_fac:
            res = await session.execute(
                select(FacultyProfile)
                .options(
                    selectinload(FacultyProfile.identifiers),
                    selectinload(FacultyProfile.name_variants),
                    selectinload(FacultyProfile.publication_links).selectinload(PublicationAuthor.publication),
                    selectinload(FacultyProfile.metric_snapshots),
                )
                .where(FacultyProfile.normalized_name.ilike("%prashant%upadhyay%"))
            )
            target_fac = res.scalars().first()
            if target_fac:
                test_faculty_ids = [target_fac.id]

        # Find 2 more active faculty with publications
        res = await session.execute(
            select(FacultyProfile.id)
            .where(FacultyProfile.status == "active")
            .where(FacultyProfile.id != test_faculty_ids[0])
            .limit(2)
        )
        for row in res.all():
            test_faculty_ids.append(row[0])

        for fac_id in test_faculty_ids:
            res = await session.execute(
                select(FacultyProfile)
                .options(
                    selectinload(FacultyProfile.publication_links).selectinload(PublicationAuthor.publication),
                    selectinload(FacultyProfile.metric_snapshots),
                )
                .where(FacultyProfile.id == fac_id)
            )
            fac = res.scalars().first()
            if not fac:
                continue

            print(f"\n--- FACULTY: {fac.raw_name} (ID: {fac.id}) ---")
            print(f"Department: {fac.department}")
            print(f"Declared Count: {fac.declared_publication_count}")
            print(f"Attributed Publications (PublicationAuthor links): {len(fac.publication_links)}")
            
            citations = []
            for link in fac.publication_links[:10]:
                pub = link.publication
                if pub:
                    citations.append(pub.citation_count or 0)
                    safe_title = pub.title.encode('ascii', 'replace').decode('ascii') if pub.title else 'No Title'
                    print(f"  - [{pub.citation_source or 'no_source'}: {pub.citation_count} cits, method={link.attribution_method}, conf={link.attribution_confidence}] {safe_title[:65]} (DOI: {pub.doi or 'None'})")

            # Snapshots
            if fac.metric_snapshots:
                latest_snap = fac.metric_snapshots[-1]
                print(f"Latest Snapshot:")
                print(f"  Total Pubs: {latest_snap.total_publications}")
                print(f"  Total Cits: {latest_snap.total_citations}")
                print(f"  h-index:    {latest_snap.h_index}")
                print(f"  i10-index:  {latest_snap.i10_index}")
            else:
                print("No metric snapshot found!")

    print("\n=======================================================")
    print("STEP 2: TESTING REST APIS VIA ASGI CLIENT")
    print("=======================================================")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Publication stats endpoint
        pub_stats_res = await client.get("/api/v1/publications/stats")
        print(f"GET /api/v1/publications/stats -> Status: {pub_stats_res.status_code}")
        print(json.dumps(pub_stats_res.json(), indent=2))

        # 2. Discovery status endpoint
        disc_status_res = await client.get("/api/v1/discovery/status")
        print(f"\nGET /api/v1/discovery/status -> Status: {disc_status_res.status_code}")
        print(json.dumps(disc_status_res.json().get("system_health", {}), indent=2))

        # 3. Test faculty endpoints for each test faculty
        for fac_id in test_faculty_ids:
            print(f"\n==========================================")
            print(f"Testing APIs for Faculty ID: {fac_id}")
            print(f"==========================================")
            
            # Faculty detail API
            fac_res = await client.get(f"/api/v1/faculty/{fac_id}")
            fac_data = fac_res.json()
            print(f"GET /api/v1/faculty/{fac_id} -> {fac_data.get('raw_name')}")
            print(f"  Metric Snapshots: {json.dumps(fac_data.get('metric_snapshots', []), indent=2)}")

            # Analytics dashboard API
            dash_res = await client.get(f"/api/v1/analytics/dashboard?faculty_id={fac_id}")
            print(f"\nGET /api/v1/analytics/dashboard?faculty_id={fac_id} ->")
            print(json.dumps(dash_res.json(), indent=2))

            # Publications list filtered by faculty_id
            pubs_res = await client.get(f"/api/v1/publications/?faculty_id={fac_id}")
            pubs_data = pubs_res.json()
            print(f"\nGET /api/v1/publications/?faculty_id={fac_id} -> Total: {pubs_data.get('total')}")
            for p in pubs_data.get("data", [])[:5]:
                print(f"    * [{p.get('citation_source', 'none')}: {p.get('citation_count', 0)} cits] {p.get('title')[:60]}")

if __name__ == "__main__":
    asyncio.run(run_verification())

