import asyncio
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import async_session_factory
from app.agents.discovery_agent import PublicationDiscoveryAgent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_agent():
    # Use SQLite for testing
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    
    # Patch SQLite for arrays/jsonb
    from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
    def visit_ARRAY(self, type_, **kw): return "JSON"
    def visit_JSONB(self, type_, **kw): return "JSON"
    SQLiteTypeCompiler.visit_ARRAY = visit_ARRAY
    SQLiteTypeCompiler.visit_JSONB = visit_JSONB
    
    sqlite_engine = create_async_engine("sqlite+aiosqlite:///seed_test.db")
    sqlite_factory = async_sessionmaker(sqlite_engine, expire_on_commit=False)
    
    # Ensure tables are created if missing (just in case)
    from app.database import Base
    async with sqlite_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with sqlite_factory() as session:
        agent = PublicationDiscoveryAgent(session)
        stats = await agent.run()
        
        logger.info("--- Publication Discovery Report ---")
        logger.info(f"Faculty processed: {stats['processed']}")
        logger.info(f"Publications discovered: {stats['publications_discovered']}")
        logger.info(f"DOIs found: {stats['dois_found']}")
        logger.info(f"Duplicates prevented: {stats['duplicates_prevented']}")
        logger.info(f"Errors encountered: {stats['errors']}")
        logger.info("------------------------------------")

if __name__ == "__main__":
    asyncio.run(run_agent())
