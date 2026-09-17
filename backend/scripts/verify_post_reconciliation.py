import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from app.database import async_session_factory
from app.models.faculty import FacultyProfile
from app.models.publication import Publication, PublicationAuthor
from app.models.review import ReviewTask
from app.models.metrics import FacultyMetricSnapshot

async def verify_post_reconciliation():
    async with async_session_factory() as session:
        # Check Siva
        siva_id = uuid.UUID('e7399ee0-758c-453b-8a96-329e3dc2cc96')
        siva = (await session.execute(select(FacultyProfile).where(FacultyProfile.id == siva_id))).scalars().first()

        # Count PublicationAuthor links
        siva_pas = (await session.execute(
            select(PublicationAuthor).options(selectinload(PublicationAuthor.publication)).where(PublicationAuthor.faculty_id == siva_id)
        )).scalars().all()

        # Count pending tasks
        siva_tasks = (await session.execute(
            select(ReviewTask).where(ReviewTask.related_entity_id == siva_id, ReviewTask.status == "pending")
        )).scalars().all()

        # Get latest snapshot
        siva_snap = (await session.execute(
            select(FacultyMetricSnapshot).where(FacultyMetricSnapshot.faculty_id == siva_id).order_by(FacultyMetricSnapshot.snapshot_date.desc())
        )).scalars().first()

        print(f"=== DR. P. SIVA PRASAD VERIFICATION ===")
        print(f"PublicationAuthor count: {len(siva_pas)}")
        for pa in siva_pas:
            print(f"  - Confirmed Pub: {pa.publication.title} | DOI: {pa.publication.doi} | Conf: {pa.attribution_confidence} | Method: {pa.attribution_method}")
        print(f"Pending candidate review tasks: {len(siva_tasks)}")
        print(f"Metric Snapshot: Pubs={siva_snap.total_publications if siva_snap else 0}, Citations={siva_snap.total_citations if siva_snap else 0}, h-index={siva_snap.h_index if siva_snap else 0}, i10-index={siva_snap.i10_index if siva_snap else 0}")

        # Target DOI check: 10.1109/iciccs67901.2026.11502731 (Sai Prasad)
        target_doi = "10.1109/iciccs67901.2026.11502731"
        target_pa = (await session.execute(
            select(PublicationAuthor).join(Publication).where(Publication.doi == target_doi, PublicationAuthor.faculty_id == siva_id)
        )).scalars().first()
        print(f"\nTarget DOI ({target_doi}) attributed to Siva? {'YES (ERROR!)' if target_pa else 'NO (CORRECT: detached/isolated)'}")

        # Check other faculty
        print(f"\n=== AUDIT FOR 5 OTHER FACULTY ===")
        sample_names = ["m umadevi", "venkatrama phani kumar s", "prashant upadhyay", "k.v. krishna kishore", "vijai meyyappan moorthy"]
        for name in sample_names:
            fac = (await session.execute(select(FacultyProfile).where(FacultyProfile.normalized_name.ilike(f"%{name}%")))).scalars().first()
            if not fac:
                continue
            pas = (await session.execute(select(PublicationAuthor).where(PublicationAuthor.faculty_id == fac.id))).scalars().all()
            tasks = (await session.execute(select(ReviewTask).where(ReviewTask.related_entity_id == fac.id, ReviewTask.status == "pending"))).scalars().all()
            snap = (await session.execute(select(FacultyMetricSnapshot).where(FacultyMetricSnapshot.faculty_id == fac.id).order_by(FacultyMetricSnapshot.snapshot_date.desc()))).scalars().first()
            print(f"\nFaculty: {fac.normalized_name} ({fac.department})")
            print(f"  PublicationAuthor count: {len(pas)}")
            print(f"  Pending candidate tasks: {len(tasks)}")
            print(f"  Snapshot: Pubs={snap.total_publications if snap else 0}, Citations={snap.total_citations if snap else 0}, h-index={snap.h_index if snap else 0}, i10-index={snap.i10_index if snap else 0}")

if __name__ == "__main__":
    asyncio.run(verify_post_reconciliation())
