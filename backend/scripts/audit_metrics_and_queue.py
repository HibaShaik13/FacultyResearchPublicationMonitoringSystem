import asyncio
import json
import sys
from sqlalchemy import select, func, or_, desc
from sqlalchemy.orm import selectinload
import httpx

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from app.database import async_session_factory
from app.models.faculty import FacultyProfile
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.metrics import FacultyMetricSnapshot, CitationSnapshot
from app.models.review import ReviewTask
from app.models.user import User
from app.core.security import create_access_token
from app.main import app

async def run_audit():
    print("===================================================================")
    print("1. DASHBOARD & FACULTY METRIC INTEGRITY FOR DR. P. SIVA PRASAD")
    print("===================================================================")
    async with async_session_factory() as session:
        stmt = (
            select(FacultyProfile)
            .options(
                selectinload(FacultyProfile.metric_snapshots),
                selectinload(FacultyProfile.publication_links).selectinload(PublicationAuthor.publication),
            )
            .where(FacultyProfile.institutional_email == "drpsp_cse@vignan.ac.in")
        )
        res = await session.execute(stmt)
        fac = res.scalars().first()
        
        if not fac:
            print("ERROR: Dr. P. Siva Prasad profile not found!")
            return

        print(f"Faculty: {fac.raw_name} (ID: {fac.id})")
        print(f"Department: {fac.department}, Designation: {fac.designation}")
        print(f"Email: {fac.institutional_email}")

        # Count unique attributed publications
        unique_pubs = {}
        for link in fac.publication_links:
            p = link.publication
            if p:
                unique_pubs[p.id] = p

        total_unique_pubs = len(unique_pubs)
        total_links = len(fac.publication_links)
        
        # Calculate citations, h-index, i10-index independently
        citations = [p.citation_count for p in unique_pubs.values() if p.citation_count is not None]
        citations_sorted = sorted(citations, reverse=True)
        total_citations = sum(citations)
        
        h_index = 0
        for i, c in enumerate(citations_sorted, 1):
            if c >= i:
                h_index = i
            else:
                break
                
        i10_index = sum(1 for c in citations if c >= 10)

        print(f"\nIndependent DB Calculation from {total_unique_pubs} unique attributed publications:")
        print(f"  Total Publications: {total_unique_pubs}")
        print(f"  Total Links: {total_links}")
        print(f"  Total Citations: {total_citations}")
        print(f"  h-index: {h_index}")
        print(f"  i10-index: {i10_index}")

        # Check Latest FacultyMetricSnapshot
        latest_snap = fac.metric_snapshots[-1] if fac.metric_snapshots else None
        if latest_snap:
            print(f"\nLatest FacultyMetricSnapshot ({latest_snap.snapshot_date}):")
            print(f"  Total Publications: {latest_snap.total_publications}")
            print(f"  Total Citations: {latest_snap.total_citations}")
            print(f"  h-index: {latest_snap.h_index}")
            print(f"  i10-index: {latest_snap.i10_index}")
            
            match_pubs = (latest_snap.total_publications == total_unique_pubs)
            match_cits = (latest_snap.total_citations == total_citations)
            match_h = (latest_snap.h_index == h_index)
            match_i10 = (latest_snap.i10_index == i10_index)
            print(f"  Snapshot matches DB: pubs={match_pubs}, cits={match_cits}, h={match_h}, i10={match_i10}")

    print("\n===================================================================")
    print("2. REVIEW TASK COUNTS & STATUS BREAKDOWN IN POSTGRESQL")
    print("===================================================================")
    async with async_session_factory() as session:
        # Total review tasks
        total_tasks = (await session.execute(select(func.count(ReviewTask.id)))).scalar()
        print(f"Total ReviewTask records in DB: {total_tasks}")

        # Group by status
        status_stmt = select(ReviewTask.status, func.count(ReviewTask.id)).group_by(ReviewTask.status)
        status_counts = dict((await session.execute(status_stmt)).all())
        print("Review Tasks by Status:", json.dumps(status_counts, indent=2))

        # Group by task_type
        type_stmt = select(ReviewTask.task_type, func.count(ReviewTask.id)).group_by(ReviewTask.task_type)
        type_counts = dict((await session.execute(type_stmt)).all())
        print("Review Tasks by Task Type:", json.dumps(type_counts, indent=2))

        # Group by decision
        decision_stmt = select(ReviewTask.decision, func.count(ReviewTask.id)).group_by(ReviewTask.decision)
        decision_counts = dict((await session.execute(decision_stmt)).all())
        print("Review Tasks by Decision:", json.dumps(decision_counts, indent=2))

        # Tasks for Dr. P. Siva Prasad (either entity_id or related_entity_id)
        siva_tasks_stmt = select(ReviewTask).where(
            or_(
                ReviewTask.entity_id == fac.id,
                ReviewTask.related_entity_id == fac.id
            )
        )
        siva_tasks = (await session.execute(siva_tasks_stmt)).scalars().all()
        print(f"\nReview Tasks for Dr. P. Siva Prasad (related_entity_id={fac.id}): {len(siva_tasks)}")
        for st in siva_tasks:
            print(f"  - [{st.status}/{st.task_type}] {st.explanation} (decision={st.decision})")

        # Tasks for other faculty
        other_tasks_stmt = select(ReviewTask).where(
            ReviewTask.related_entity_id != fac.id
        )
        other_tasks_count = len((await session.execute(other_tasks_stmt)).scalars().all())
        print(f"Review Tasks for other faculty / general: {other_tasks_count}")

    print("\n===================================================================")
    print("3. SAMPLE RECENT REVIEW TASKS IN POSTGRESQL (5 Records)")
    print("===================================================================")
    async with async_session_factory() as session:
        stmt = (
            select(ReviewTask)
            .order_by(desc(ReviewTask.created_at))
            .limit(5)
        )
        tasks = (await session.execute(stmt)).scalars().all()
        for t in tasks:
            # fetch publication if entity is publication
            pub_title = "N/A"
            if t.entity_type == "publication" and t.entity_id:
                p_res = await session.execute(select(Publication.title).where(Publication.id == t.entity_id))
                pub_title = p_res.scalar() or "Unknown Title"
            
            # fetch faculty if related_entity_id
            fac_name = "N/A"
            if t.related_entity_id:
                f_res = await session.execute(select(FacultyProfile.raw_name).where(FacultyProfile.id == t.related_entity_id))
                fac_name = f_res.scalar() or "Unknown Faculty"

            print(f"ReviewTask ID: {t.id}")
            print(f"  Publication ID: {t.entity_id}")
            print(f"  Publication Title: {pub_title}")
            print(f"  Faculty ID: {t.related_entity_id}")
            print(f"  Faculty Name: {fac_name}")
            print(f"  Task Type: {t.task_type}")
            print(f"  Priority: {t.priority}")
            print(f"  Status: {t.status}")
            print(f"  Decision: {t.decision}")
            print(f"  Explanation: {t.explanation}")
            print(f"  Created At: {t.created_at}")
            print(f"  Decided At: {t.decided_at}")
            print()

    print("\n===================================================================")
    print("4. API ENDPOINT AUDIT: ADMIN VS FACULTY ROLE")
    print("===================================================================")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Create token for admin
        admin_token = create_access_token(data={"sub": "admin@vignan.ac.in", "role": "admin"})
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Create token for Dr. P. Siva Prasad (faculty)
        siva_token = create_access_token(data={"sub": "drpsp_cse@vignan.ac.in", "role": "faculty", "faculty_id": str(fac.id)})
        siva_headers = {"Authorization": f"Bearer {siva_token}"}

        # A. Call /api/v1/review/stats as Admin
        admin_stats_res = await client.get("/api/v1/review/stats", headers=admin_headers)
        print(f"GET /api/v1/review/stats (as ADMIN) -> Status: {admin_stats_res.status_code}")
        print("  Admin Stats:", json.dumps(admin_stats_res.json(), indent=2))

        # B. Call /api/v1/review/queue as Admin
        admin_queue_res = await client.get("/api/v1/review/queue?status=pending", headers=admin_headers)
        admin_queue_data = admin_queue_res.json()
        print(f"\nGET /api/v1/review/queue?status=pending (as ADMIN) -> Status: {admin_queue_res.status_code}, Count: {len(admin_queue_data)}")

        # C. Call /api/v1/review/stats as Faculty (Dr. P. Siva Prasad)
        fac_stats_res = await client.get("/api/v1/review/stats", headers=siva_headers)
        print(f"\nGET /api/v1/review/stats (as DR. P. SIVA PRASAD - faculty role) -> Status: {fac_stats_res.status_code}")
        print("  Faculty Stats:", json.dumps(fac_stats_res.json(), indent=2))

        # D. Call /api/v1/review/queue as Faculty (Dr. P. Siva Prasad)
        fac_queue_res = await client.get("/api/v1/review/queue?status=pending", headers=siva_headers)
        fac_queue_data = fac_queue_res.json()
        print(f"\nGET /api/v1/review/queue?status=pending (as DR. P. SIVA PRASAD - faculty role) -> Status: {fac_queue_res.status_code}, Count: {len(fac_queue_data)}")

    print("\n===================================================================")
    print("5. CITATION 0 VS UNAVAILABLE ANALYSIS (10 Sample Publications)")
    print("===================================================================")
    async with async_session_factory() as session:
        zero_stmt = (
            select(Publication)
            .options(selectinload(Publication.sources), selectinload(Publication.citation_snapshots))
            .where(Publication.citation_count == 0)
            .limit(10)
        )
        zero_pubs = (await session.execute(zero_stmt)).scalars().all()
        for zp in zero_pubs:
            source_names = [s.source_system for s in zp.sources]
            has_explicit_snap = any(sn.citation_count == 0 for sn in zp.citation_snapshots)
            print(f"  * DOI: {zp.doi or 'None'}")
            print(f"    Title: {zp.title[:70]}")
            print(f"    citation_count: {zp.citation_count}")
            print(f"    citation_source: {zp.citation_source}")
            print(f"    sources linked: {source_names}")
            print(f"    explicit 0 snapshot present: {has_explicit_snap}")
            print()

    print("\n===================================================================")
    print("6. SYSTEM TOTALS & ACCIDENTAL DATA LOSS CHECK")
    print("===================================================================")
    async with async_session_factory() as session:
        faculty_count = (await session.execute(select(func.count(FacultyProfile.id)))).scalar()
        publication_count = (await session.execute(select(func.count(Publication.id)))).scalar()
        author_link_count = (await session.execute(select(func.count(PublicationAuthor.id)))).scalar()
        review_count = (await session.execute(select(func.count(ReviewTask.id)))).scalar()
        snapshot_count = (await session.execute(select(func.count(FacultyMetricSnapshot.id)))).scalar()

        print(f"Total Faculty Profiles: {faculty_count}")
        print(f"Total Publications: {publication_count}")
        print(f"Total PublicationAuthor links: {author_link_count}")
        print(f"Total ReviewTask records: {review_count}")
        print(f"Total FacultyMetricSnapshots: {snapshot_count}")

if __name__ == "__main__":
    asyncio.run(run_audit())
