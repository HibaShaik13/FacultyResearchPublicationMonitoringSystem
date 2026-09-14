import asyncio
import json
import logging
import os
import sys

from sqlalchemy.ext.asyncio import AsyncSession

# Add the project root to sys.path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import async_session_factory
from app.seed.csv_importer import FacultyCSVParser, FacultyImporter

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def seed_data():
    csv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw", "faculty_profiles.csv"))
    
    if not os.path.exists(csv_path):
        logger.error(f"CSV file not found at {csv_path}")
        return

    logger.info(f"Parsing CSV at {csv_path}")
    parser = FacultyCSVParser(csv_path)
    records = parser.parse()
    
    logger.info(f"Parsed {len(records)} records. Importing into database...")
    
    async with async_session_factory() as session:
        importer = FacultyImporter(session)
        stats = await importer.run(records)
        
        logger.info("Import complete.")
        logger.info("--- Import Report ---")
        logger.info(f"Total processed: {stats['total_processed']}")
        logger.info(f"Imported successfully: {stats['imported']}")
        logger.info(f"Skipped duplicates: {stats['skipped_duplicates']}")
        logger.info(f"Name variants created: {stats['variants_created']}")
        logger.info(f"Errors encountered: {stats['errors']}")
        logger.info("---------------------")


if __name__ == "__main__":
    asyncio.run(seed_data())
