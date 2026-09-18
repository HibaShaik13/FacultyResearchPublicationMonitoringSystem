"""
Production database bootstrap and account seeding script.

Idempotent: safe to run multiple times. Run after `alembic upgrade head`.
Provisions:
  1. Faculty profiles from data/raw/faculty_profiles.csv (if not already imported)
  2. Faculty publications from data/raw/faculty_publications.csv (deduplicated & linked to faculty)
  3. Research Admin user account (configurable via BOOTSTRAP_ADMIN_EMAIL / BOOTSTRAP_ADMIN_PASSWORD)
  4. Faculty user accounts linked to faculty profiles (configurable via BOOTSTRAP_FACULTY_PASSWORD)
  5. Faculty metrics calculation and verification

Usage:
  python -m app.seed.bootstrap
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.config import get_settings
from app.core.security import hash_password
from app.database import async_session_factory
from app.models.faculty import FacultyProfile
from app.models.metrics import FacultyMetricSnapshot
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.user import User
from app.seed.csv_importer import (
    FacultyCSVParser,
    FacultyImporter,
    PublicationCSVParser,
    PublicationImporter,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bootstrap")


def locate_profiles_csv_path() -> Optional[Path]:
    """Locate data/raw/faculty_profiles.csv across multiple execution contexts."""
    env_override = os.getenv("FACULTY_PROFILES_CSV_PATH")
    if env_override and Path(env_override).is_file():
        return Path(env_override)

    candidates = [
        Path("data/raw/faculty_profiles.csv"),
        Path("../data/raw/faculty_profiles.csv"),
        Path("../../data/raw/faculty_profiles.csv"),
        backend_dir.parent / "data" / "raw" / "faculty_profiles.csv",
        backend_dir / "data" / "raw" / "faculty_profiles.csv",
    ]

    for c in candidates:
        if c.is_file():
            return c.resolve()

    return None


locate_csv_path = locate_profiles_csv_path


def locate_publications_csv_path() -> Optional[Path]:
    """Locate data/raw/faculty_publications.csv across multiple execution contexts."""
    env_override = os.getenv("FACULTY_PUBLICATIONS_CSV_PATH")
    if env_override and Path(env_override).is_file():
        return Path(env_override)

    candidates = [
        Path("data/raw/faculty_publications.csv"),
        Path("../data/raw/faculty_publications.csv"),
        Path("../../data/raw/faculty_publications.csv"),
        backend_dir.parent / "data" / "raw" / "faculty_publications.csv",
        backend_dir / "data" / "raw" / "faculty_publications.csv",
    ]

    for c in candidates:
        if c.is_file():
            return c.resolve()

    return None


async def seed_faculty_profiles(session: AsyncSession) -> int:
    """Import faculty profiles from CSV if not already present."""
    csv_path = locate_profiles_csv_path()
    if not csv_path:
        logger.warning("faculty_profiles.csv not found in candidate paths. Skipping profile import.")
        return 0

    logger.info(f"Parsing faculty profiles from {csv_path}")
    parser = FacultyCSVParser(str(csv_path))
    records = parser.parse()

    importer = FacultyImporter(session)
    stats = await importer.run(records)
    logger.info(
        f"Faculty profile import complete: processed={stats['total_processed']}, "
        f"imported={stats['imported']}, skipped_existing={stats['skipped_duplicates']}, "
        f"variants={stats['variants_created']}, errors={stats['errors']}"
    )
    return stats["imported"]


async def seed_faculty_publications(session: AsyncSession) -> dict:
    """Import publications from CSV and link authors to FacultyProfile."""
    csv_path = locate_publications_csv_path()
    if not csv_path:
        logger.warning("faculty_publications.csv not found in candidate paths. Skipping publication import.")
        return {"total_processed": 0, "publications_created": 0, "author_links_created": 0}

    logger.info(f"Parsing faculty publications from {csv_path}")
    parser = PublicationCSVParser(str(csv_path))
    records = parser.parse()

    importer = PublicationImporter(session)
    stats = await importer.run(records)
    logger.info(
        f"Publication import complete: processed={stats['total_processed']}, "
        f"created={stats['publications_created']}, reused={stats['publications_reused']}, "
        f"author_links_created={stats['author_links_created']}, "
        f"author_links_skipped={stats['author_links_skipped']}, "
        f"unmatched_faculty={stats['unmatched_faculty']}, errors={stats['errors']}"
    )
    return stats


async def seed_admin_user(session: AsyncSession, settings) -> bool:
    """Seed system research_admin user if not already present."""
    admin_email = settings.bootstrap_admin_email.strip().lower()
    stmt = select(User).where(func.lower(User.email) == admin_email)
    res = await session.execute(stmt)
    existing_admin = res.scalars().first()

    admin_pwd_hash = hash_password(settings.bootstrap_admin_password)

    if existing_admin:
        existing_admin.password_hash = admin_pwd_hash
        existing_admin.is_active = True
        existing_admin.role = "research_admin"
        await session.commit()
        logger.info(f"Admin user already exists ({admin_email}). Password and active status synchronized.")
        return False

    admin_user = User(
        email=admin_email,
        full_name=settings.bootstrap_admin_name,
        role="research_admin",
        password_hash=admin_pwd_hash,
        is_active=True,
    )
    session.add(admin_user)
    await session.commit()
    logger.info(f"Successfully created admin user ({admin_email}) with role=research_admin.")
    return True


async def seed_faculty_users(session: AsyncSession, settings) -> dict:
    """Create user accounts for all faculty profiles and link faculty_id with idempotent password sync."""
    stmt = select(FacultyProfile)
    res = await session.execute(stmt)
    profiles = res.scalars().all()

    created_count = 0
    updated_count = 0
    existing_count = 0

    faculty_pwd_hash = hash_password(settings.bootstrap_faculty_password)

    for profile in profiles:
        email = (profile.institutional_email or profile.raw_email or "").strip().lower()
        if not email:
            logger.warning(f"Profile {profile.id} ({profile.raw_name}) has no email. Skipping user creation.")
            continue

        u_stmt = select(User).where(func.lower(User.email) == email)
        u_res = await session.execute(u_stmt)
        user = u_res.scalars().first()

        if not user:
            new_user = User(
                email=email,
                full_name=profile.raw_name,
                role="faculty",
                faculty_id=profile.id,
                password_hash=faculty_pwd_hash,
                is_active=True,
            )
            session.add(new_user)
            created_count += 1
        else:
            existing_count += 1
            # Ensure faculty_id is linked and seeded faculty accounts have valid password hash and active status
            if user.faculty_id != profile.id or not user.is_active:
                user.faculty_id = profile.id
                user.is_active = True
                updated_count += 1
            if user.role == "faculty":
                user.password_hash = faculty_pwd_hash

    await session.commit()
    logger.info(
        f"Faculty user seeding complete: created={created_count}, "
        f"already_existing={existing_count}, updated={updated_count}"
    )
    return {
        "created": created_count,
        "already_existing": existing_count,
        "updated": updated_count,
    }


async def log_summary(session: AsyncSession):
    """Log safe counts and verification stats."""
    faculty_count = (await session.execute(select(func.count(FacultyProfile.id)))).scalar() or 0
    users_count = (await session.execute(select(func.count(User.id)))).scalar() or 0
    pubs_count = (await session.execute(select(func.count(Publication.id)))).scalar() or 0
    links_count = (await session.execute(select(func.count(PublicationAuthor.id)))).scalar() or 0
    sources_count = (await session.execute(select(func.count(PublicationSource.id)))).scalar() or 0
    metrics_count = (await session.execute(select(func.count(FacultyMetricSnapshot.id)))).scalar() or 0

    logger.info("================ BOOTSTRAP DATABASE SUMMARY ================")
    logger.info(f"Faculty profiles:         {faculty_count}")
    logger.info(f"User accounts:            {users_count}")
    logger.info(f"Publications:             {pubs_count}")
    logger.info(f"Publication-author links: {links_count}")
    logger.info(f"Publication sources:      {sources_count}")
    logger.info(f"Faculty metric snapshots: {metrics_count}")
    logger.info("============================================================")


async def ensure_baseline_accounts(session: AsyncSession) -> dict:
    """
    Idempotent, transaction-safe startup assurance:
    1. Ensures all FacultyProfile records exist from CSV (skips existing, adds missing).
    2. Ensures Research Admin user exists (creates or activates).
    3. Ensures every FacultyProfile has an active User account with valid password_hash.
    4. Ensures Publication records exist if table is empty.
    
    Safe to run on every application startup. Never deletes or overwrites existing valid passwords.
    """
    settings = get_settings()
    
    # 1. Profiles (FacultyImporter skips duplicates and only inserts missing profiles)
    if settings.bootstrap_seed_faculty:
        await seed_faculty_profiles(session)
        
    # 2. Admin User
    admin_email = settings.bootstrap_admin_email.strip().lower()
    admin_stmt = select(User).where(func.lower(User.email) == admin_email)
    admin_user = (await session.execute(admin_stmt)).scalars().first()
    if not admin_user:
        logger.info(f"Startup: Admin user {admin_email} missing. Provisioning...")
        await seed_admin_user(session, settings)
    elif not admin_user.is_active:
        admin_user.is_active = True
        await session.commit()
        
    # 3. Faculty Users
    profiles = (await session.execute(select(FacultyProfile))).scalars().all()
    faculty_pwd_hash = hash_password(settings.bootstrap_faculty_password)
    users_created = 0
    
    for profile in profiles:
        email = (profile.institutional_email or profile.raw_email or "").strip().lower()
        if not email:
            continue
        
        u_stmt = select(User).where(func.lower(User.email) == email)
        user = (await session.execute(u_stmt)).scalars().first()
        
        if not user:
            new_user = User(
                email=email,
                full_name=profile.raw_name,
                role="faculty",
                faculty_id=profile.id,
                password_hash=faculty_pwd_hash,
                is_active=True,
            )
            session.add(new_user)
            users_created += 1
        else:
            # Ensure binding and active status
            if user.faculty_id != profile.id:
                user.faculty_id = profile.id
            if not user.is_active:
                user.is_active = True
            if not user.password_hash:
                user.password_hash = faculty_pwd_hash
    
    await session.commit()
    if users_created > 0:
        logger.info(f"Startup: Provisioned {users_created} missing faculty user accounts.")

    # 4. Publications (only if table completely empty)
    pub_count = (await session.execute(select(func.count(Publication.id)))).scalar() or 0
    if pub_count == 0 and settings.bootstrap_seed_publications:
        logger.info("Startup: No publications found. Seeding initial publications from CSV...")
        await seed_faculty_publications(session)
        
    return {"status": "success", "faculty_profiles": len(profiles), "new_users": users_created}


async def trigger_initial_research_pipeline_if_needed() -> None:
    """
    Checks if an initial full research synchronization is needed on startup (Phase 2C).
    If full_sync has never completed and none is currently active, triggers PipelineOrchestrator
    in the background without blocking application startup or health endpoints.
    """
    try:
        from app.orchestrator.pipeline_orchestrator import PipelineOrchestrator
        async with async_session_factory() as session:
            orchestrator = PipelineOrchestrator(session)
            has_run = await orchestrator.has_initial_sync_completed()
            is_running = await orchestrator.is_sync_running()

            if not has_run and not is_running:
                logger.info(
                    "Startup: No prior completed full research sync detected. "
                    "Launching autonomous initial research pipeline in background..."
                )
                await asyncio.sleep(2)  # Brief pause to yield control to event loop & let server start
                stats = await orchestrator.run_full_pipeline(trigger="startup_autonomous_initial_discovery")
                logger.info(
                    f"Startup: Autonomous initial research pipeline finished: status={stats.get('sync_run_status')} "
                    f"(errors={stats.get('total_errors', 0)})"
                )
            elif is_running:
                logger.info("Startup: An active research pipeline is already running. Skipping duplicate startup trigger.")
            else:
                logger.info("Startup: Prior research synchronization detected in database. Skipping duplicate initial discovery.")
    except Exception as e:
        logger.error(f"Startup: Autonomous initial research pipeline encountered an error: {e}", exc_info=True)


async def run_bootstrap():
    """Main bootstrap entry point."""
    settings = get_settings()
    logger.info("Starting production database bootstrap...")

    async with async_session_factory() as session:
        await ensure_baseline_accounts(session)
        await log_summary(session)

    logger.info("Production database bootstrap finished successfully.")


if __name__ == "__main__":
    asyncio.run(run_bootstrap())

