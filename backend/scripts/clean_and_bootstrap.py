import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import delete, select, func
from app.database import async_session_factory
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.metrics import FacultyMetricSnapshot
from app.seed.bootstrap import run_bootstrap

async def reset_and_bootstrap():
    async with async_session_factory() as session:
        print("Cleaning duplicate publications from test runs...")
        await session.execute(delete(PublicationSource))
        await session.execute(delete(PublicationAuthor))
        await session.execute(delete(Publication))
        await session.execute(delete(FacultyMetricSnapshot))
        await session.commit()
    
    print("Running idempotent bootstrap...")
    await run_bootstrap()

if __name__ == "__main__":
    asyncio.run(reset_and_bootstrap())
