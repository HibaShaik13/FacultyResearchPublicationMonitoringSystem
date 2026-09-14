import asyncio
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import async_session_factory
from app.agents.identity_agent import FacultyIdentityAgent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_agent():
    # Use SQLite for testing since Postgres is not available
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    
    # We don't need to patch the compiler here because we are only reading/writing FacultyIdentifier
    # and ReviewTask which don't have ARRAY/JSONB issues with SQLite, wait, ReviewTask has JSONB!
    # Let's patch it just in case.
    from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
    def visit_ARRAY(self, type_, **kw): return "JSON"
    def visit_JSONB(self, type_, **kw): return "JSON"
    SQLiteTypeCompiler.visit_ARRAY = visit_ARRAY
    SQLiteTypeCompiler.visit_JSONB = visit_JSONB
    from app.models.faculty import FacultyProfile
    from sqlalchemy.types import JSON
    FacultyProfile.__table__.c.research_interests.type = JSON()
    
    sqlite_engine = create_async_engine("sqlite+aiosqlite:///seed_test.db")
    sqlite_factory = async_sessionmaker(sqlite_engine, expire_on_commit=False)
    
    async with sqlite_factory() as session:
        agent = FacultyIdentityAgent(session)
        stats = await agent.run()
        
        logger.info("--- Identity Resolution Report ---")
        logger.info(f"Total faculty processed: {stats['processed']}")
        logger.info(f"Identities matched (auto-verified): {stats['matched']}")
        logger.info(f"Ambiguous matches (queued for review): {stats['ambiguous']}")
        logger.info(f"Unmatched faculty: {stats['unmatched']}")
        logger.info(f"Errors encountered: {stats['errors']}")
        logger.info("----------------------------------")

if __name__ == "__main__":
    asyncio.run(run_agent())
