import asyncio
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, r"c:\Users\muska\OneDrive\Desktop\ResearchFacultyMonitoringSystem\backend")

from app.database import async_session_factory
from app.models.faculty import FacultyProfile
from app.models.publication import Publication, PublicationAuthor
from app.models.metrics import FacultyMetricSnapshot, CitationSnapshot
from app.models.user import User
from app.models.review import ReviewTask

async def inspect_db():
    async with async_session_factory() as db:
        # Count records
        faculty_count = (await db.execute(select(func.count(FacultyProfile.id)))).scalar()
        user_count = (await db.execute(select(func.count(User.id)))).scalar()
        
        users_with_faculty = (await db.execute(
            select(func.count(User.id)).where(User.faculty_id.isnot(None))
        )).scalar()
        
        pub_count = (await db.execute(select(func.count(Publication.id)))).scalar()
        pub_author_count = (await db.execute(select(func.count(PublicationAuthor.id)))).scalar()
        review_count = (await db.execute(select(func.count(ReviewTask.id)))).scalar()
        fac_metric_count = (await db.execute(select(func.count(FacultyMetricSnapshot.id)))).scalar()
        cit_snap_count = (await db.execute(select(func.count(CitationSnapshot.id)))).scalar()
        
        print("--- DATABASE STATS ---")
        print(f"Faculty records: {faculty_count}")
        print(f"User records: {user_count}")
        print(f"Users linked to faculty: {users_with_faculty}")
        print(f"Publications: {pub_count}")
        print(f"PublicationAuthors: {pub_author_count}")
        print(f"Review tasks: {review_count}")
        print(f"Faculty metric snapshots: {fac_metric_count}")
        print(f"Citation snapshots: {cit_snap_count}")
        
        print("\n--- UMADEVI RECORD ---")
        # Find Umadevi
        query = select(FacultyProfile).where(FacultyProfile.raw_name.ilike("%umadevi%")).options(
            selectinload(FacultyProfile.metric_snapshots),
        )
        result = await db.execute(query)
        umadevi = result.scalars().first()
        
        if umadevi:
            print(f"ID: {umadevi.id}")
            print(f"Name: {umadevi.raw_name}")
            print(f"Email: {umadevi.institutional_email}")
            
            # Attributed pubs
            pubs = (await db.execute(
                select(func.count(PublicationAuthor.publication_id))
                .where(PublicationAuthor.faculty_id == umadevi.id)
            )).scalar()
            print(f"Attributed Publications (via PublicationAuthor): {pubs}")
            
            if umadevi.metric_snapshots:
                latest = umadevi.metric_snapshots[0]
                print(f"Citations: {latest.total_citations}")
                print(f"h-index: {latest.h_index}")
                print(f"i10-index: {latest.i10_index}")
            else:
                print("Citations: None")
                print("h-index: None")
                print("i10-index: None")
                
            tasks = (await db.execute(
                select(func.count(ReviewTask.id))
                .where(ReviewTask.subject_id == str(umadevi.id))
            )).scalar()
            print(f"Review Tasks (subject_id=faculty_id): {tasks}")
        else:
            print("Umadevi not found!")

if __name__ == "__main__":
    asyncio.run(inspect_db())
