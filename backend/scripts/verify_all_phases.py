import asyncio
import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import select, func
from app.database import async_session_factory
from app.models.user import User
from app.models.faculty import FacultyProfile
from app.models.publication import Publication, PublicationAuthor
from app.models.metrics import FacultyMetricSnapshot
from app.core.security import verify_password, create_access_token, decode_token
from app.config import get_settings

async def verify_all():
    settings = get_settings()
    print("Settings JWT algorithm:", settings.jwt_algorithm)
    print("Settings CORS origins:", settings.backend_cors_origins)

    async with async_session_factory() as session:
        # 1. Admin account check
        admin_res = await session.execute(
            select(User).where(func.lower(User.email) == settings.bootstrap_admin_email.lower())
        )
        admin = admin_res.scalars().first()
        assert admin is not None, "Admin user missing"
        assert verify_password(settings.bootstrap_admin_password, admin.password_hash), "Admin password mismatch"
        print("[PASS] Admin user verified:", admin.email, "role:", admin.role)

        # 2. Dr M Umadevi Check
        uma_res = await session.execute(
            select(User).where(func.lower(User.email) == "druma_cse@vignan.ac.in")
        )
        uma_user = uma_res.scalars().first()
        assert uma_user is not None, "Dr M Umadevi user account missing"
        assert verify_password("faculty123", uma_user.password_hash), "Dr M Umadevi password verification failed"
        assert uma_user.faculty_id is not None, "Dr M Umadevi faculty_id link missing"
        print(f"[PASS] Dr M Umadevi user: {uma_user.email}, faculty_id: {uma_user.faculty_id}")

        # Check Faculty Profile
        prof_res = await session.execute(
            select(FacultyProfile).where(FacultyProfile.id == uma_user.faculty_id)
        )
        uma_prof = prof_res.scalars().first()
        assert uma_prof is not None, "Dr M Umadevi profile missing"
        print(f"[PASS] Dr M Umadevi profile: {uma_prof.raw_name}, email: {uma_prof.institutional_email}")

        # Check Publications count for Dr M Umadevi
        pubs_res = await session.execute(
            select(Publication)
            .join(Publication.authors)
            .where(PublicationAuthor.faculty_id == uma_user.faculty_id)
        )
        uma_pubs = pubs_res.scalars().unique().all()
        print(f"[PASS] Dr M Umadevi publications count in database: {len(uma_pubs)}")
        assert len(uma_pubs) == 17, f"Expected 17 publications for Dr M Umadevi, got {len(uma_pubs)}"

        # Check Metric Snapshot
        snap_res = await session.execute(
            select(FacultyMetricSnapshot)
            .where(FacultyMetricSnapshot.faculty_id == uma_user.faculty_id)
            .order_by(FacultyMetricSnapshot.snapshot_date.desc())
        )
        uma_snap = snap_res.scalars().first()
        assert uma_snap is not None, "Metric snapshot missing for Dr M Umadevi"
        print(f"[PASS] Dr M Umadevi metrics snapshot: total_publications={uma_snap.total_publications}, total_citations={uma_snap.total_citations}, h_index={uma_snap.h_index}")
        assert uma_snap.total_publications == 17, f"Snapshot publications mismatch: {uma_snap.total_publications}"

        # 3. Check All 24 Faculty Accounts
        all_fac_users = (await session.execute(
            select(User).where(User.role == "faculty")
        )).scalars().all()
        print(f"[PASS] Total seeded faculty users in database: {len(all_fac_users)}")
        assert len(all_fac_users) == 24, f"Expected 24 faculty users, got {len(all_fac_users)}"

        for u in all_fac_users:
            assert u.faculty_id is not None, f"User {u.email} has no linked faculty_id"
            assert u.is_active is True, f"User {u.email} is inactive"
            assert verify_password("faculty123", u.password_hash), f"User {u.email} password verification failed"

            # Check token generation and decoding
            token = create_access_token(data={"sub": u.email, "role": u.role})
            payload = decode_token(token)
            assert payload is not None and payload["sub"] == u.email, f"JWT verification failed for {u.email}"

        print("[PASS] All 24 faculty users validated for password, active status, faculty_id linkage, and JWT generation/decoding!")

if __name__ == "__main__":
    asyncio.run(verify_all())
