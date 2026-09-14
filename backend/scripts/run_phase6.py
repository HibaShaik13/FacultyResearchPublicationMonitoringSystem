import asyncio
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import async_session_factory
from app.agents.attribution_agent import FacultyAttributionAgent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_agents():
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
    
    async with sqlite_factory() as session:
        # Agent 6
        attribution_agent = FacultyAttributionAgent(session)
        stats = await attribution_agent.run()
        
        logger.info("--- Phase 6 Execution Report ---")
        logger.info("Faculty Attribution:")
        logger.info(f"  Processed: {stats['processed']}")
        logger.info(f"  Attributions created: {stats['attributions_created']}")
        logger.info(f"  High confidence: {stats['high_confidence']}")
        logger.info(f"  Ambiguous (ReviewTasks): {stats['ambiguous']}")
        logger.info(f"  Errors: {stats['errors']}")
        logger.info("--------------------------------")

if __name__ == "__main__":
    asyncio.run(run_agents())
