"""
Production database bootstrap and account seeding script.

Idempotent: safe to run multiple times. Run after `alembic upgrade head`.
Provisions:
  1. Faculty profiles from data/raw/faculty_profiles.csv (if not already imported)
  2. Research Admin user account (configurable via BOOTSTRAP_ADMIN_EMAIL / BOOTSTRAP_ADMIN_PASSWORD)
  3. Faculty user accounts linked to faculty profiles (configurable via BOOTSTRAP_FACULTY_PASSWORD)

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
from app.models.user import User
from app.seed.csv_importer import FacultyCSVParser, FacultyImporter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bootstrap")


def locate_csv_path() -> Optional[Path]:
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


async def seed_faculty_profiles(session: AsyncSession) -> int:
    """Import faculty profiles from CSV if table is empty or missing profiles."""
    csv_path = locate_csv_path()
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


async def seed_admin_user(session: AsyncSession, settings) -> bool:
    """Seed system research_admin user if not already present."""
    admin_email = settings.bootstrap_admin_email.strip().lower()
    stmt = select(User).where(func.lower(User.email) == admin_email)
    res = await session.execute(stmt)
    existing_admin = res.scalars().first()

    if existing_admin:
        logger.info(f"Admin user already exists ({admin_email}). Skipping creation.")
        return False

    admin_user = User(
        email=admin_email,
        full_name=settings.bootstrap_admin_name,
        role="research_admin",
        password_hash=hash_password(settings.bootstrap_admin_password),
        is_active=True,
    )
    session.add(admin_user)
    await session.commit()
    logger.info(f"Successfully created admin user ({admin_email}) with role=research_admin.")
    return True


async def seed_faculty_users(session: AsyncSession, settings) -> dict:
    """Create user accounts for all faculty profiles and link faculty_id."""
    stmt = select(FacultyProfile)
    res = await session.execute(stmt)
    profiles = res.scalars().all()

    created_count = 0
    linked_count = 0
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
            if user.faculty_id is None:
                user.faculty_id = profile.id
                linked_count += 1

    await session.commit()
    logger.info(
        f"Faculty user seeding complete: created={created_count}, "
        f"already_existing={existing_count}, newly_linked={linked_count}"
    )
    return {
        "created": created_count,
        "already_existing": existing_count,
        "newly_linked": linked_count,
    }


async def run_bootstrap():
    """Main bootstrap entry point."""
    settings = get_settings()
    logger.info("Starting production database bootstrap...")

    async with async_session_factory() as session:
        # Step 1: Faculty Profiles
        if settings.bootstrap_seed_faculty:
            await seed_faculty_profiles(session)

        # Step 2: Research Admin User
        await seed_admin_user(session, settings)

        # Step 3: Faculty Users
        await seed_faculty_users(session, settings)

    logger.info("Production database bootstrap finished successfully.")


if __name__ == "__main__":
    asyncio.run(run_bootstrap())
