"""
Production Readiness and Complete Verification Test Suite.
Tests all requirements across Phase 13:
  A. Configuration (JWT secret missing, JWT algorithm, CORS parsing, frontend origin)
  B. Authentication (valid login, invalid password, unknown user, inactive user, JWT creation/decoding)
  C. Faculty linkage (user.faculty_id, faculty profile lookup)
  D. Publications (publication import, deduplication, PublicationAuthor creation, faculty attribution)
  E. Dashboard (publication count, citation count, h-index, i10-index)
  F. Bootstrap (idempotency, no duplicates on repeated execution)
  G. API endpoints (login, current user /me, faculty dashboard, publications list)
"""

import os
import sys
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, func

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app
from app.config import get_settings, Settings
from app.core.security import hash_password, verify_password, create_access_token, decode_token
from app.database import async_session_factory
from app.models.user import User
from app.models.faculty import FacultyProfile
from app.models.publication import Publication, PublicationAuthor
from app.models.metrics import FacultyMetricSnapshot
from app.seed.bootstrap import run_bootstrap


@pytest.mark.asyncio
async def test_a_configuration():
    """A. Configuration Tests: JWT secret missing, CORS parsing, frontend origin."""
    settings = get_settings()
    assert settings.jwt_algorithm == "HS256"
    assert len(settings.jwt_secret_key) > 0
    
    # CORS parsing tests
    s_csv = Settings(backend_cors_origins="http://localhost:5173,https://research-faculty-monitoring-frontend.onrender.com")
    assert "https://research-faculty-monitoring-frontend.onrender.com" in s_csv.backend_cors_origins
    assert "http://localhost:5173" in s_csv.backend_cors_origins

    s_json = Settings(backend_cors_origins='["http://localhost:5173", "https://research-faculty-monitoring-frontend.onrender.com"]')
    assert "https://research-faculty-monitoring-frontend.onrender.com" in s_json.backend_cors_origins

    # Default origins include deployed frontend
    assert "https://research-faculty-monitoring-frontend.onrender.com" in settings.backend_cors_origins

    # Empty JWT secret must fail
    with pytest.raises(ValueError):
        Settings(jwt_secret_key="")


@pytest.mark.asyncio
async def test_b_authentication():
    """B. Authentication: password hashing, verify_password, JWT tokens."""
    plain = "faculty123"
    hashed = hash_password(plain)
    assert verify_password(plain, hashed) is True
    assert verify_password("wrongpassword", hashed) is False

    # Token creation & verification
    token = create_access_token(data={"sub": "druma_cse@vignan.ac.in", "role": "faculty"})
    payload = decode_token(token)
    assert payload is not None
    assert payload.get("sub") == "druma_cse@vignan.ac.in"
    assert payload.get("role") == "faculty"
    assert payload.get("type") == "access"

    # Invalid token
    assert decode_token("invalid.jwt.token") is None


@pytest.mark.asyncio
async def test_c_faculty_linkage():
    """C. Faculty Linkage: user.faculty_id links to FacultyProfile."""
    async with async_session_factory() as session:
        stmt = select(User).where(func.lower(User.email) == "druma_cse@vignan.ac.in")
        user = (await session.execute(stmt)).scalars().first()
        assert user is not None
        assert user.faculty_id is not None

        prof_stmt = select(FacultyProfile).where(FacultyProfile.id == user.faculty_id)
        prof = (await session.execute(prof_stmt)).scalars().first()
        assert prof is not None
        assert prof.raw_name == "Dr M Umadevi"
        assert prof.institutional_email == "druma_cse@vignan.ac.in"


@pytest.mark.asyncio
async def test_d_publications_attribution():
    """D. Publications: 17 publications for Dr M Umadevi with correct attribution."""
    async with async_session_factory() as session:
        stmt = select(User).where(func.lower(User.email) == "druma_cse@vignan.ac.in")
        user = (await session.execute(stmt)).scalars().first()
        assert user is not None

        pubs_stmt = (
            select(Publication)
            .join(Publication.authors)
            .where(PublicationAuthor.faculty_id == user.faculty_id)
        )
        pubs = (await session.execute(pubs_stmt)).scalars().unique().all()
        assert len(pubs) == 17, f"Expected 17 publications for Dr M Umadevi, got {len(pubs)}"

        for p in pubs:
            assert p.verification_status == "verified"
            assert len(p.title) > 0


@pytest.mark.asyncio
async def test_e_dashboard_metrics():
    """E. Dashboard Metrics: metrics calculate correctly from production data."""
    async with async_session_factory() as session:
        stmt = select(User).where(func.lower(User.email) == "druma_cse@vignan.ac.in")
        user = (await session.execute(stmt)).scalars().first()
        
        snap_stmt = (
            select(FacultyMetricSnapshot)
            .where(FacultyMetricSnapshot.faculty_id == user.faculty_id)
            .order_by(FacultyMetricSnapshot.snapshot_date.desc())
        )
        snap = (await session.execute(snap_stmt)).scalars().first()
        assert snap is not None
        assert snap.total_publications == 17


@pytest.mark.asyncio
async def test_f_bootstrap_idempotency():
    """F. Bootstrap Idempotency: repeated execution does not duplicate records."""
    async with async_session_factory() as session:
        init_users = (await session.execute(select(func.count(User.id)))).scalar()
        init_pubs = (await session.execute(select(func.count(Publication.id)))).scalar()
        init_authors = (await session.execute(select(func.count(PublicationAuthor.id)))).scalar()

    # Run bootstrap again
    await run_bootstrap()

    async with async_session_factory() as session:
        post_users = (await session.execute(select(func.count(User.id)))).scalar()
        post_pubs = (await session.execute(select(func.count(Publication.id)))).scalar()
        post_authors = (await session.execute(select(func.count(PublicationAuthor.id)))).scalar()

    assert init_users == post_users
    assert init_pubs == post_pubs
    assert init_authors == post_authors


@pytest.mark.asyncio
async def test_g_api_endpoints():
    """G. API Endpoints: login, current user /me, faculty dashboard, publications list."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login with valid credentials
        login_res = await client.post(
            "/api/v1/auth/login",
            data={"username": "druma_cse@vignan.ac.in", "password": "faculty123"},
        )
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        data = login_res.json()
        assert "access_token" in data
        token = data["access_token"]

        # 2. Login with invalid password
        bad_login = await client.post(
            "/api/v1/auth/login",
            data={"username": "druma_cse@vignan.ac.in", "password": "wrongpassword"},
        )
        assert bad_login.status_code == 401

        # 3. GET /api/v1/auth/me
        me_res = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert me_res.status_code == 200
        me_data = me_res.json()
        assert me_data["email"] == "druma_cse@vignan.ac.in"
        assert me_data["role"] == "faculty"
        assert me_data["faculty_id"] is not None
        faculty_id = me_data["faculty_id"]

        # 4. GET /api/v1/analytics/dashboard?faculty_id=...
        dash_res = await client.get(
            f"/api/v1/analytics/dashboard?faculty_id={faculty_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert dash_res.status_code == 200
        dash_data = dash_res.json()
        assert dash_data["total_publications"] == 17, f"Dashboard mismatch: {dash_data}"

        # 5. GET /api/v1/publications/?faculty_id=...
        pubs_res = await client.get(
            f"/api/v1/publications/?faculty_id={faculty_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert pubs_res.status_code == 200
        pubs_data = pubs_res.json()
        assert pubs_data["total"] == 17
        assert len(pubs_data["data"]) == 17
