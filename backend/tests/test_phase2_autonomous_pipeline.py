"""
Phase 2 Autonomous Research Monitoring Pipeline & Initialization Integration Tests.
"""

import asyncio
import json
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler

from app.database import Base
from app.models.agent import SyncRun, AgentRun
from app.models.faculty import FacultyProfile, FacultyIdentifier
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.provenance import ProvenanceRecord
from app.models.user import User
from app.config import Settings
from app.orchestrator.pipeline_orchestrator import PipelineOrchestrator
from app.connectors.vidwan import VidwanClient
from app.agents.discovery_agent import PublicationDiscoveryAgent
import app.seed.bootstrap as bootstrap

# Register SQLite adapters for testing
sqlite3.register_adapter(list, json.dumps)
sqlite3.register_adapter(dict, json.dumps)
SQLiteTypeCompiler.visit_ARRAY = lambda self, type_, **kw: "JSON"
SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "JSON"


@pytest.fixture
async def async_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield session_factory

    await engine.dispose()


@pytest.mark.asyncio
async def test_stale_run_recovery(async_db):
    """Test Phase 2D: Stale runs are recovered and marked failed without deleting historical records."""
    async with async_db() as session:
        stale_time = datetime.now(timezone.utc) - timedelta(minutes=45)
        stale_run = SyncRun(
            id=uuid.uuid4(),
            run_type="full_sync",
            status="running",
            trigger="startup_autonomous_initial_discovery",
            started_at=stale_time,
        )
        session.add(stale_run)
        await session.commit()

        orchestrator = PipelineOrchestrator(session)
        recovered = await orchestrator.recover_stale_runs(stale_threshold_minutes=30)
        assert recovered == 1

        # Check stale run record is preserved
        stmt = select(SyncRun).where(SyncRun.id == stale_run.id)
        run = (await session.execute(stmt)).scalars().first()
        assert run is not None
        assert run.status == "failed"
        assert run.completed_at is not None
        assert run.errors_count >= 1


@pytest.mark.asyncio
async def test_duplicate_pipeline_protection(async_db):
    """Test Phase 2C / 2D: Concurrency protection prevents duplicate simultaneous full sync runs."""
    async with async_db() as session:
        active_run = SyncRun(
            id=uuid.uuid4(),
            run_type="full_sync",
            status="running",
            trigger="scheduled",
            started_at=datetime.now(timezone.utc),
        )
        session.add(active_run)
        await session.commit()

        orchestrator = PipelineOrchestrator(session)
        res = await orchestrator.run_full_pipeline(trigger="admin_manual", allow_concurrent=False)
        assert res.get("status") == "skipped_duplicate"
        assert "already in progress" in res.get("message", "")


@pytest.mark.asyncio
async def test_vidwan_connector_resilience():
    """Test Vidwan connector parsing and error isolation."""
    client = VidwanClient(timeout=5.0)

    # 1. Invalid ID handling
    pubs = await client.get_profile_publications("invalid-id-xyz")
    assert pubs == []

    # 2. HTML parsing check
    sample_html = """
    <html>
    <body>
        <div class="publication">
            <h5>Machine Learning in Cryptography</h5>
            <span>Dr P. Siva Prasad, 2024, 10.1109/sample.2024.12345</span>
        </div>
        <div class="publication">
            <h5>Algebraic Structures in Cyber Security</h5>
            <span>P. Siva Prasad, 2023, Journal of Applied Mathematics</span>
        </div>
    </body>
    </html>
    """
    parsed = client._parse_profile_html(sample_html, "84197", "https://vidwan.inflibnet.ac.in/profile/84197")
    assert len(parsed) == 2
    assert "Machine Learning" in parsed[0]["title"]
    assert parsed[0]["doi"] == "10.1109/sample.2024.12345"
    assert parsed[0]["year"] == 2024
    assert parsed[0]["vidwan_id"] == "84197"


@pytest.mark.asyncio
async def test_controlled_discovery_deduplication(async_db):
    """Test Phase 2F: Discovered publications are normalized and deduplicated across multiple sources."""
    async with async_db() as session:
        # Create a faculty profile
        fac_id = uuid.uuid4()
        faculty = FacultyProfile(
            id=fac_id,
            raw_name="Dr P. Siva Prasad",
            normalized_name="p. siva prasad",
            raw_email="drpsp_cse@vignan.ac.in",
            institutional_email="drpsp_cse@vignan.ac.in",
            status="active"
        )
        session.add(faculty)
        await session.commit()

        discovery = PublicationDiscoveryAgent(session)

        # Ingest publication from Source 1 (Crossref)
        stats = {
            "processed": 0,
            "publications_discovered": 0,
            "dois_found": 0,
            "duplicates_prevented": 0,
            "errors": 0,
            "sources_queried": {},
        }
        await discovery._create_publication(
            profile=faculty,
            title="Smart Attendance System Using Face Recognition",
            doi="10.1109/icssas68835.2026.11559393",
            year=2026,
            source_system="crossref",
            source_id="10.1109/icssas68835.2026.11559393",
            raw_metadata={"title": ["Smart Attendance System Using Face Recognition"]},
            stats=stats,
            is_verified_author=True,
        )
        await session.commit()

        # Ingest same publication from Source 2 (IEEE) with same DOI
        await discovery._create_publication(
            profile=faculty,
            title="Smart Attendance System using MERN Stack and Real-Time Face Recognition",
            doi="10.1109/icssas68835.2026.11559393",
            year=2026,
            source_system="ieee",
            source_id="11559393",
            raw_metadata={"title": "Smart Attendance System using MERN Stack and Real-Time Face Recognition"},
            stats=stats,
            is_verified_author=True,
        )
        await session.commit()

        # Assert: Exactly 1 canonical publication, with 2 publication sources
        pub_stmt = select(Publication)
        pubs = (await session.execute(pub_stmt)).scalars().all()
        assert len(pubs) == 1
        assert pubs[0].doi == "10.1109/icssas68835.2026.11559393"

        src_stmt = select(PublicationSource).where(PublicationSource.publication_id == pubs[0].id)
        sources = (await session.execute(src_stmt)).scalars().all()
        assert len(sources) == 2
        source_systems = {s.source_system for s in sources}
        assert source_systems == {"crossref", "ieee"}

        # Assert: PublicationAuthor attribution is linked
        auth_stmt = select(PublicationAuthor).where(PublicationAuthor.publication_id == pubs[0].id)
        authors = (await session.execute(auth_stmt)).scalars().all()
        assert len(authors) == 1
        assert authors[0].faculty_id == fac_id


@pytest.mark.asyncio
async def test_baseline_25_faculty_and_siva_presence(async_db):
    """Test Phase 2A/2B: Baseline seed loads 25 faculty including Dr. P. Siva Prasad with valid account."""
    settings = Settings(
        bootstrap_admin_email="admin@vignan.ac.in",
        bootstrap_admin_password="test_admin_pwd",
        bootstrap_faculty_password="test_fac_pwd",
        bootstrap_seed_faculty=True,
    )

    async with async_db() as session:
        # 1. Seed baseline accounts
        res = await bootstrap.ensure_baseline_accounts(session)
        assert res["status"] == "success"
        assert res["faculty_profiles"] == 25

        # 2. Verify Siva profile
        siva_prof_stmt = select(FacultyProfile).where(FacultyProfile.institutional_email == "drpsp_cse@vignan.ac.in")
        siva_prof = (await session.execute(siva_prof_stmt)).scalars().first()
        assert siva_prof is not None
        assert siva_prof.raw_name == "Dr P. Siva Prasad"

        # 3. Verify Siva user account
        siva_user_stmt = select(User).where(User.email == "drpsp_cse@vignan.ac.in")
        siva_user = (await session.execute(siva_user_stmt)).scalars().first()
        assert siva_user is not None
        assert siva_user.faculty_id == siva_prof.id
        assert siva_user.is_active is True
        assert siva_user.role == "faculty"

        # 4. Total user count: 25 faculty + 1 admin = 26
        user_count = (await session.execute(select(func.count(User.id)))).scalar()
        assert user_count == 26
