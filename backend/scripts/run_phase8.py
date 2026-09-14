import asyncio
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import async_session_factory
from app.agents.integrity_agent import ResearchIntegrityAgent

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
    
    # Add adapters for SQLite
    import sqlite3
    import json
    sqlite3.register_adapter(list, json.dumps)
    sqlite3.register_adapter(dict, json.dumps)
    
    sqlite_engine = create_async_engine("sqlite+aiosqlite:///seed_test.db")
    sqlite_factory = async_sessionmaker(sqlite_engine, expire_on_commit=False)
    
    async with sqlite_factory() as session:
        # Agent 8
        agent = ResearchIntegrityAgent(session)
        stats = await agent.run()
        
        logger.info("--- Phase 8 Execution Report ---")
        logger.info("Research Integrity:")
        logger.info(f"  Processed: {stats['processed']}")
        logger.info(f"  LOW Risk: {stats['low']}")
        logger.info(f"  MEDIUM Risk: {stats['medium']}")
        logger.info(f"  HIGH Risk: {stats['high']}")
        logger.info(f"  ReviewTasks Created: {stats['review_required']}")
        logger.info(f"  Issues Detected: {stats['issues_detected']}")
        logger.info(f"  Errors: {stats['errors']}")
        logger.info("--------------------------------")

if __name__ == "__main__":
    asyncio.run(run_agents())
