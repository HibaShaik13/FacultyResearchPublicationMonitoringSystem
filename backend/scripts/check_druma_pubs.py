import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import async_session_factory
from app.models.publication import Publication, PublicationAuthor
from app.models.faculty import FacultyProfile
from sqlalchemy import select

async def check():
    async with async_session_factory() as session:
        res = await session.execute(select(FacultyProfile).where(FacultyProfile.raw_name == 'Dr M Umadevi'))
        prof = res.scalars().first()
        print('Profile ID:', prof.id)
        
        auth_res = await session.execute(
            select(PublicationAuthor, Publication)
            .join(Publication, PublicationAuthor.publication_id == Publication.id)
            .where(PublicationAuthor.faculty_id == prof.id)
        )
        rows = auth_res.all()
        print(f'Total linked rows: {len(rows)}')
        for i, (pa, p) in enumerate(rows):
            print(f'{i+1}. Author raw: "{pa.author_name_raw}" | method: "{pa.attribution_method}" | Title: "{p.title[:80]}"')

if __name__ == "__main__":
    asyncio.run(check())
