import asyncio
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import async_session_factory
from app.agents.metadata_normalization_agent import MetadataNormalizationAgent
from app.agents.deduplication_agent import DeduplicationAgent

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
        # Agent 4
        norm_agent = MetadataNormalizationAgent(session)
        norm_stats = await norm_agent.run()
        
        # Agent 5
        dedup_agent = DeduplicationAgent(session)
        dedup_stats = await dedup_agent.run()
        
        logger.info("--- Phase 5 Execution Report ---")
        logger.info("Metadata Normalization:")
        logger.info(f"  Processed: {norm_stats['processed']}")
        logger.info(f"  Normalized: {norm_stats['normalized']}")
        logger.info(f"  Errors: {norm_stats['errors']}")
        
        logger.info("Deduplication & Resolution:")
        logger.info(f"  Processed: {dedup_stats['processed']}")
        logger.info(f"  Merged: {dedup_stats['merged']}")
        logger.info(f"  Ambiguous (ReviewTasks created): {dedup_stats['ambiguous']}")
        logger.info(f"  Errors: {dedup_stats['errors']}")
        logger.info("--------------------------------")

if __name__ == "__main__":
    asyncio.run(run_agents())
