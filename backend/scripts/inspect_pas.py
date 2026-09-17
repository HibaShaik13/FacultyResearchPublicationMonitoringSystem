import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import async_session_factory
from app.models.faculty import FacultyProfile
from app.models.publication import Publication, PublicationAuthor

async def inspect_raw_authors():
    async with async_session_factory() as session:
        fac_stmt = select(FacultyProfile).where(FacultyProfile.normalized_name.ilike("%siva prasad%"))
        fac = (await session.execute(fac_stmt)).scalars().first()

        stmt = select(PublicationAuthor).where(PublicationAuthor.faculty_id == fac.id)
        pas = (await session.execute(stmt)).scalars().all()

        author_raw_counts = {}
        for p in pas:
            raw = p.author_name_raw or "<EMPTY>"
            author_raw_counts[raw] = author_raw_counts.get(raw, 0) + 1

        print("author_name_raw in PublicationAuthor:")
        for k, v in author_raw_counts.items():
            print(f"  {k}: {v}")

if __name__ == "__main__":
    asyncio.run(inspect_raw_authors())
