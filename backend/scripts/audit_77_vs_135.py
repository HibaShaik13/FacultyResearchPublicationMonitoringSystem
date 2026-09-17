import asyncio
import json
import sys
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from app.database import async_session_factory
from app.models.faculty import FacultyProfile
from app.models.publication import Publication, PublicationAuthor
from app.models.review import ReviewTask
from app.models.metrics import FacultyMetricSnapshot

async def audit():
    fac_id = "e7399ee0-758c-453b-8a96-329e3dc2cc96"
    
    async with async_session_factory() as session:
        # 1. Get faculty and his 90 attributed publications
        fac = await session.get(FacultyProfile, fac_id)
        auth_stmt = select(PublicationAuthor.publication_id).where(
            PublicationAuthor.faculty_id == fac_id
        )
        faculty_pub_ids = (await session.execute(auth_stmt)).scalars().all()
        print(f"Faculty: {fac.raw_name} ({fac.id})")
        print(f"Total Attributed Publications in PublicationAuthor: {len(faculty_pub_ids)}")

        # 2. Detailed Breakdown of Categories
        # A: Tasks where related_entity_id == Siva's faculty ID
        stmt_a = select(ReviewTask).where(ReviewTask.status == "pending", ReviewTask.related_entity_id == fac_id)
        tasks_a = (await session.execute(stmt_a)).scalars().all()
        
        # B: Tasks where entity_id == Siva's faculty ID
        stmt_b = select(ReviewTask).where(ReviewTask.status == "pending", ReviewTask.entity_id == fac_id)
        tasks_b = (await session.execute(stmt_b)).scalars().all()

        # C: Tasks where entity_id in Siva's publication IDs
        stmt_c = select(ReviewTask).where(ReviewTask.status == "pending", ReviewTask.entity_id.in_(faculty_pub_ids))
        tasks_c = (await session.execute(stmt_c)).scalars().all()

        print(f"\n--- BREAKDOWN BY CRITERIA ---")
        print(f"Category A (related_entity_id == Siva): {len(tasks_a)} tasks")
        print(f"Category B (entity_id == Siva): {len(tasks_b)} tasks")
        print(f"Category C (entity_id in Siva's 90 attributed publications): {len(tasks_c)} tasks")

        # Overlaps
        set_a = set(t.id for t in tasks_a)
        set_b = set(t.id for t in tasks_b)
        set_c = set(t.id for t in tasks_c)

        print(f"Overlap (A & C): {len(set_a & set_c)}")
        print(f"Union (A | B | C): {len(set_a | set_b | set_c)}")
        print(f"Old Union (B | C): {len(set_b | set_c)}")

        # 3. Analyze Task Types in Category A (related_entity_id == Siva)
        type_counts_a = {}
        for t in tasks_a:
            type_counts_a[t.task_type] = type_counts_a.get(t.task_type, 0) + 1
        print(f"\nTask Types in Category A (related_entity_id == Siva):", json.dumps(type_counts_a, indent=2))

        # 4. Analyze Task Types in Category C (entity_id in Siva's 90 publications)
        type_counts_c = {}
        for t in tasks_c:
            type_counts_c[t.task_type] = type_counts_c.get(t.task_type, 0) + 1
        print(f"\nTask Types in Category C (entity_id in Siva's 90 publications):", json.dumps(type_counts_c, indent=2))

        # In Category C, which faculty are in related_entity_id?
        other_faculty_in_c = {}
        for t in tasks_c:
            if t.related_entity_id != fac.id and t.related_entity_id is not None:
                other_faculty_in_c[str(t.related_entity_id)] = other_faculty_in_c.get(str(t.related_entity_id), 0) + 1
            elif t.related_entity_id is None:
                other_faculty_in_c["None (General/Metadata)"] = other_faculty_in_c.get("None (General/Metadata)", 0) + 1
        print(f"\nIn Category C, breakdown of related_entity_id (target of the review):", json.dumps(other_faculty_in_c, indent=2))

        # 5. Exact explanation of 77 vs 135
        print("\n===================================================================")
        print("EXACT MATHEMATICAL DERIVATION:")
        print(f"Old filter: entity_id IN (90 pubs) OR entity_id == Siva")
        print(f"  -> Count = {len(set_b | set_c)} (= 77)")
        print(f"  -> Breakdown of 77:")
        for k, v in type_counts_c.items():
            print(f"     - {k}: {v}")
        if len(tasks_b) > 0:
            print(f"     - entity_id == Siva: {len(tasks_b)}")

        print(f"\nNew filter: entity_id IN (90 pubs) OR entity_id == Siva OR related_entity_id == Siva")
        print(f"  -> Count = {len(set_a | set_b | set_c)} (= 135)")
        print(f"  -> Additional tasks added: {len(set_a - set_c)} tasks where related_entity_id == Siva but publication is not yet in his 90 attributed publications!")

        # 6. Verify Dashboard Metrics
        snap_stmt = select(FacultyMetricSnapshot).where(FacultyMetricSnapshot.faculty_id == fac_id).order_by(FacultyMetricSnapshot.snapshot_date.desc()).limit(1)
        snap = (await session.execute(snap_stmt)).scalars().first()
        print("\n===================================================================")
        print("DASHBOARD METRICS INTEGRITY CHECK:")
        print(f"  Total Publications: {snap.total_publications} (Expected: 90)")
        print(f"  Total Citations: {snap.total_citations} (Expected: 913)")
        print(f"  h-index: {snap.h_index} (Expected: 13)")
        print(f"  i10-index: {snap.i10_index} (Expected: 14)")

if __name__ == "__main__":
    asyncio.run(audit())
