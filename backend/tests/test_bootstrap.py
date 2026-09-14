"""
Unit and integration tests for production bootstrap seeding.
"""

import json
import sqlite3
import pytest
from unittest.mock import MagicMock
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler

from app.database import Base
from app.models.faculty import FacultyProfile
from app.models.user import User
from app.config import Settings
from app.core.security import verify_password
import app.seed.bootstrap as bootstrap

# Register SQLite adapters for testing
sqlite3.register_adapter(list, json.dumps)
sqlite3.register_adapter(dict, json.dumps)
SQLiteTypeCompiler.visit_ARRAY = lambda self, type_, **kw: "JSON"
SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "JSON"


def test_locate_csv_path():
    path = bootstrap.locate_csv_path()
    assert path is not None
    assert path.is_file()
    assert "faculty_profiles.csv" in str(path)


@pytest.mark.asyncio
async def test_bootstrap_idempotent_flow():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    settings = Settings(
        bootstrap_admin_email="admin@vignan.ac.in",
        bootstrap_admin_password="test_admin_pwd",
        bootstrap_admin_name="Dr. Hiba",
        bootstrap_faculty_password="test_fac_pwd",
        bootstrap_seed_faculty=True,
    )

    # Initial Run
    async with session_factory() as session:
        profiles_imported = await bootstrap.seed_faculty_profiles(session)
        assert profiles_imported == 24

        admin_created = await bootstrap.seed_admin_user(session, settings)
        assert admin_created is True

        fac_stats = await bootstrap.seed_faculty_users(session, settings)
        assert fac_stats["created"] == 24

    # Verify Run 1 Data
    async with session_factory() as session:
        admin_res = await session.execute(select(User).where(User.email == "admin@vignan.ac.in"))
        admin = admin_res.scalars().first()
        assert admin is not None
        assert admin.role == "research_admin"
        assert verify_password("test_admin_pwd", admin.password_hash) is True

        fac_res = await session.execute(select(User).where(User.email == "druma_cse@vignan.ac.in"))
        faculty = fac_res.scalars().first()
        assert faculty is not None
        assert faculty.role == "faculty"
        assert faculty.faculty_id is not None
        assert verify_password("test_fac_pwd", faculty.password_hash) is True

        count_res = await session.execute(select(func.count(User.id)))
        assert count_res.scalar() == 25

    # Second Run (Idempotency Check)
    async with session_factory() as session:
        profiles_run2 = await bootstrap.seed_faculty_profiles(session)
        assert profiles_run2 == 0

        admin_run2 = await bootstrap.seed_admin_user(session, settings)
        assert admin_run2 is False

        fac_stats_run2 = await bootstrap.seed_faculty_users(session, settings)
        assert fac_stats_run2["created"] == 0
        assert fac_stats_run2["already_existing"] == 24

    # Verify Count Remains 25
    async with session_factory() as session:
        count_res2 = await session.execute(select(func.count(User.id)))
        assert count_res2.scalar() == 25

    await engine.dispose()


@pytest.mark.asyncio
async def test_auth_login_api_flow():
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.database import get_db

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    settings = Settings(
        bootstrap_admin_email="admin@vignan.ac.in",
        bootstrap_admin_password="admin",
        bootstrap_faculty_password="faculty123",
        bootstrap_seed_faculty=True,
    )

    # Seed
    async with session_factory() as session:
        await bootstrap.seed_faculty_profiles(session)
        await bootstrap.seed_admin_user(session, settings)
        await bootstrap.seed_faculty_users(session, settings)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Admin login success
        res = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin@vignan.ac.in", "password": "admin"},
        )
        assert res.status_code == 200, res.text
        tokens = res.json()
        assert "access_token" in tokens
        admin_token = tokens["access_token"]

        # Admin /me
        me_res = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert me_res.status_code == 200
        admin_data = me_res.json()
        assert admin_data["email"] == "admin@vignan.ac.in"
        assert admin_data["role"] == "research_admin"
        assert admin_data["faculty_id"] is None

        # 2. Faculty login success
        f_res = await client.post(
            "/api/v1/auth/login",
            data={"username": "druma_cse@vignan.ac.in", "password": "faculty123"},
        )
        assert f_res.status_code == 200, f_res.text
        f_tokens = f_res.json()
        assert "access_token" in f_tokens
        f_token = f_tokens["access_token"]

        # Faculty /me
        f_me = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {f_token}"},
        )
        assert f_me.status_code == 200
        f_data = f_me.json()
        assert f_data["email"] == "druma_cse@vignan.ac.in"
        assert f_data["role"] == "faculty"
        assert f_data["faculty_id"] is not None

        # 3. Invalid password failure
        bad_res = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin@vignan.ac.in", "password": "wrongpassword"},
        )
        assert bad_res.status_code == 401

    app.dependency_overrides.clear()
    await engine.dispose()
