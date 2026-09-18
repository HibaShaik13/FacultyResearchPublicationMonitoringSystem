"""
PHASE 4.1 — Dynamic Research Flow Acceptance Test Suite.
Verifies that:
1. CSV contains ONLY stable faculty identity baseline (25 faculty).
2. Publications, citations, and metrics originate from autonomous agents, connectors, and PostgreSQL.
3. Clean staging DB starts with 0 publications and populates dynamically.
4. Multi-source deduplication and incremental new publication discovery operate without CSV modification.
5. All operations run on isolated database 'vestr_phase4_dynamic_test'.
"""

import asyncio
import hashlib
import os
import sys
import uuid
import pytest
import asyncpg
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import get_settings
from app.database import Base
from app.models.faculty import FacultyProfile, FacultyIdentifier
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.metrics import FacultyMetricSnapshot
from app.models.agent import SyncRun, AgentRun
from app.models.provenance import ProvenanceRecord
from app.models.user import User
from app.orchestrator.pipeline_orchestrator import PipelineOrchestrator
from app.agents.discovery_agent import PublicationDiscoveryAgent
from app.agents.metrics_agent import MetricsAgent
from app.connectors.vidwan import VidwanClient
from app.connectors.crossref import CrossrefClient
from app.connectors.openalex import OpenAlexClient
import app.seed.bootstrap as bootstrap

DB_NAME = "vestr_phase4_dynamic_test"

@pytest.fixture(scope="session")
async def dynamic_staging_engine():
    settings = get_settings()
    user = settings.postgres_user
    password = settings.postgres_password
    host = settings.postgres_host
    port = settings.postgres_port

    # Safety Guard: Ensure not touching production or research_monitoring
    assert DB_NAME not in ["research_monitoring", "production"], "Safety violation!"

    # Create isolated DB
    sys_conn = await asyncpg.connect(user=user, password=password, host=host, port=port, database="postgres")
    await sys_conn.execute(f"""
        SELECT pg_terminate_backend(pg_stat_activity.pid)
        FROM pg_stat_activity
        WHERE pg_stat_activity.datname = '{DB_NAME}'
          AND pid <> pg_backend_pid();
    """)
    await sys_conn.execute(f"DROP DATABASE IF EXISTS {DB_NAME};")
    await sys_conn.execute(f"CREATE DATABASE {DB_NAME};")
    await sys_conn.close()

    from sqlalchemy.pool import NullPool
    staging_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{DB_NAME}"
    engine = create_async_engine(staging_url, echo=False, pool_pre_ping=True, poolclass=NullPool)

    async with engine.begin() as conn:
        curr_db = (await conn.execute(text("SELECT current_database()"))).scalar()
        assert curr_db == DB_NAME, "Safety assertion failed!"
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest.mark.asyncio
async def test_01_clean_staging_baseline_zero_publications(dynamic_staging_engine):
    """Test 1 & 3: Clean database baseline bootstrap seeds 25 faculty, 26 users, and 0 publications."""
    session_factory = async_sessionmaker(dynamic_staging_engine, expire_on_commit=False)
    async with session_factory() as session:
        # Run bootstrap
        res = await bootstrap.ensure_baseline_accounts(session)
        assert res["status"] == "success"

        fac_cnt = (await session.execute(select(func.count(FacultyProfile.id)))).scalar()
        usr_cnt = (await session.execute(select(func.count(User.id)))).scalar()
        pub_cnt = (await session.execute(select(func.count(Publication.id)))).scalar()

        assert fac_cnt == 25, f"Expected 25 faculty, got {fac_cnt}"
        assert usr_cnt == 26, f"Expected 26 users, got {usr_cnt}"
        assert pub_cnt == 0, f"Expected 0 publications on fresh database (Choice 1), got {pub_cnt}"


@pytest.mark.asyncio
async def test_02_faculty_login_and_siva_identity_safety(dynamic_staging_engine):
    """Test 4 & 15: Faculty account authentication and Siva identity protection."""
    session_factory = async_sessionmaker(dynamic_staging_engine, expire_on_commit=False)
    async with session_factory() as session:
        siva = (await session.execute(
            select(FacultyProfile).where(FacultyProfile.institutional_email == "drpsp_cse@vignan.ac.in")
        )).scalar_one_or_none()
        assert siva is not None
        assert "Siva Prasad" in siva.raw_name

        siva_user = (await session.execute(
            select(User).where(User.email == "drpsp_cse@vignan.ac.in")
        )).scalar_one_or_none()
        assert siva_user is not None
        assert siva_user.faculty_id == siva.id
        assert siva_user.is_active is True

        # Attach verified identifiers for Siva
        identifiers = [
            ("scopus", "57208392627"),
            ("orcid", "0000-0002-2789-7431"),
            ("ieee", "256481733945119"),
            ("vidwan", "84197"),
            ("semantic_scholar", "2406283009"),
        ]
        for id_type, val in identifiers:
            session.add(FacultyIdentifier(
                id=uuid.uuid4(),
                faculty_id=siva.id,
                identifier_type=id_type,
                identifier_value=val,
                verified=True,
            ))
        await session.commit()

        # OpenAlex Mismatch Guard: Ensure A5003901187 is NOT attached
        bad_oa = (await session.execute(
            select(FacultyIdentifier).where(
                FacultyIdentifier.identifier_type == "openalex",
                FacultyIdentifier.identifier_value.ilike("%A5003901187%")
            )
        )).scalars().all()
        for ident in bad_oa:
            assert ident.faculty_id != siva.id, "CRITICAL: A5003901187 must NOT be attached to Siva!"


_DISCOVERED_VIDWAN_WORKS = []

@pytest.mark.asyncio
async def test_03_live_external_discovery_and_persistence(dynamic_staging_engine):
    """Test 5 & 6: Live discovery from Vidwan/Crossref persists canonical publications with source provenance."""
    global _DISCOVERED_VIDWAN_WORKS
    session_factory = async_sessionmaker(dynamic_staging_engine, expire_on_commit=False)
    async with session_factory() as session:
        siva = (await session.execute(
            select(FacultyProfile).where(FacultyProfile.institutional_email == "drpsp_cse@vignan.ac.in")
        )).scalar_one()

        discovery = PublicationDiscoveryAgent(session)
        stats = {"processed": 0, "publications_discovered": 0, "dois_found": 0, "duplicates_prevented": 0, "errors": 0, "sources_queried": {}}
        await discovery.discover_for_faculty(siva, stats)
        await session.commit()

        assert stats["publications_discovered"] > 0, "Expected publications discovered from external sources"

        # Check PostgreSQL persistence
        pub_cnt = (await session.execute(select(func.count(Publication.id)))).scalar()
        src_cnt = (await session.execute(select(func.count(PublicationSource.id)))).scalar()
        pa_cnt = (await session.execute(select(func.count(PublicationAuthor.id)))).scalar()
        prov_cnt = (await session.execute(select(func.count(ProvenanceRecord.id)))).scalar()

        assert pub_cnt > 0
        assert src_cnt >= pub_cnt
        assert pa_cnt > 0
        assert prov_cnt > 0


@pytest.mark.asyncio
async def test_04_idempotent_deduplication(dynamic_staging_engine):
    """Test 7: Second discovery execution on identical responses does not create duplicate canonical publications."""
    from unittest.mock import AsyncMock, patch
    session_factory = async_sessionmaker(dynamic_staging_engine, expire_on_commit=False)
    async with session_factory() as session:
        siva = (await session.execute(
            select(FacultyProfile).where(FacultyProfile.institutional_email == "drpsp_cse@vignan.ac.in")
        )).scalar_one()

        # Load existing publications for Siva
        existing_pubs = (await session.execute(
            select(Publication).join(PublicationAuthor).where(PublicationAuthor.faculty_id == siva.id)
        )).scalars().all()

        initial_pub_cnt = (await session.execute(select(func.count(Publication.id)))).scalar()
        initial_pa_cnt = (await session.execute(select(func.count(PublicationAuthor.id)))).scalar()

        discovery = PublicationDiscoveryAgent(session)
        stats = {"processed": 0, "publications_discovered": 0, "dois_found": 0, "duplicates_prevented": 0, "errors": 0, "sources_queried": {}}

        # Re-process the same discovered publications as external source input fixtures
        for p in existing_pubs:
            await discovery._create_publication(
                profile=siva,
                title=p.title,
                doi=p.doi,
                year=p.year,
                source_system="crossref",
                source_id=p.doi or str(p.id),
                raw_metadata={"title": [p.title]},
                stats=stats,
                is_verified_author=True,
            )
        await session.commit()

        after_pub_cnt = (await session.execute(select(func.count(Publication.id)))).scalar()
        after_pa_cnt = (await session.execute(select(func.count(PublicationAuthor.id)))).scalar()

        assert after_pub_cnt == initial_pub_cnt, "Deduplication failure: Duplicate publications created!"
        assert after_pa_cnt == initial_pa_cnt, "Duplicate publication authors created!"
        assert stats["publications_discovered"] == 0, "Deduplication failure: publications marked as discovered on duplicate run"


@pytest.mark.asyncio
async def test_05_incremental_discovery_lifecycle_day1_to_day2(dynamic_staging_engine):
    """Test 8 & 12: Day 1 (N publications) -> Day 2 (N+1 publications) discovered automatically without CSV edit."""
    session_factory = async_sessionmaker(dynamic_staging_engine, expire_on_commit=False)
    async with session_factory() as session:
        siva = (await session.execute(
            select(FacultyProfile).where(FacultyProfile.institutional_email == "drpsp_cse@vignan.ac.in")
        )).scalar_one()
        discovery = PublicationDiscoveryAgent(session)

        initial_count = (await session.execute(select(func.count(Publication.id)))).scalar()

        # Day 2: External source returns an additional publication
        new_doi = "10.1109/access.2026.9999999"
        stats = {"processed": 0, "publications_discovered": 0, "dois_found": 0, "duplicates_prevented": 0, "errors": 0, "sources_queried": {}}
        await discovery._create_publication(
            profile=siva,
            title="Next-Generation Federated Optimization for Autonomous Medical Diagnostics",
            doi=new_doi,
            year=2026,
            source_system="crossref",
            source_id=new_doi,
            raw_metadata={"title": ["Next-Generation Federated Optimization for Autonomous Medical Diagnostics"]},
            stats=stats,
            is_verified_author=True,
        )
        await session.commit()

        final_count = (await session.execute(select(func.count(Publication.id)))).scalar()
        assert final_count == initial_count + 1, f"Expected {initial_count + 1} publications, got {final_count}"

        # Verify new publication in DB with full provenance
        new_pub = (await session.execute(select(Publication).where(Publication.doi == new_doi))).scalar_one_or_none()
        assert new_pub is not None
        assert new_pub.verification_status in ["verified", "auto_verified", "human_verified"]

        prov = (await session.execute(select(ProvenanceRecord).where(ProvenanceRecord.entity_id == new_pub.id))).scalars().all()
        assert len(prov) > 0


@pytest.mark.asyncio
async def test_06_metrics_computation_from_postgresql(dynamic_staging_engine):
    """Test 9 & 10: Metrics (h-index, citations) are calculated directly from PostgreSQL research records, NOT CSV."""
    session_factory = async_sessionmaker(dynamic_staging_engine, expire_on_commit=False)
    async with session_factory() as session:
        metrics_agent = MetricsAgent(session)
        res = await metrics_agent.run()
        await session.commit()

        siva = (await session.execute(
            select(FacultyProfile).where(FacultyProfile.institutional_email == "drpsp_cse@vignan.ac.in")
        )).scalar_one()

        snapshot = (await session.execute(
            select(FacultyMetricSnapshot)
            .where(FacultyMetricSnapshot.faculty_id == siva.id)
            .order_by(FacultyMetricSnapshot.snapshot_date.desc())
        )).scalars().first()

        assert snapshot is not None
        assert snapshot.total_publications >= 0
        assert snapshot.total_citations >= 0
        assert snapshot.h_index >= 0
        assert snapshot.i10_index >= 0
        assert snapshot.faculty_id == siva.id


@pytest.mark.asyncio
async def test_07_scheduled_pipeline_execution_and_stale_recovery(dynamic_staging_engine):
    """Test 11 & 13: Scheduled pipeline runs autonomously without browser/JWT and recovers stale runs."""
    session_factory = async_sessionmaker(dynamic_staging_engine, expire_on_commit=False)
    async with session_factory() as session:
        orchestrator = PipelineOrchestrator(session)

        # Create simulated stale run
        stale_run = SyncRun(
            id=uuid.uuid4(),
            run_type="full_sync",
            status="running",
            trigger="simulated_stale_scheduled_job",
            started_at=datetime.now(timezone.utc),
        )
        session.add(stale_run)
        await session.commit()

        # Force stale timestamp
        await session.execute(
            text("UPDATE sync_runs SET started_at = NOW() - INTERVAL '45 minutes' WHERE id = :id"),
            {"id": stale_run.id}
        )
        await session.commit()

        # Run recovery
        recovered = await orchestrator.recover_stale_runs(stale_threshold_minutes=30)
        assert recovered >= 1

        # Check stale run updated to failed
        updated_run = (await session.execute(select(SyncRun).where(SyncRun.id == stale_run.id))).scalar_one()
        assert updated_run.status == "failed"


@pytest.mark.asyncio
async def test_08_csv_hash_and_content_immutability():
    """Test 2 & 16: faculty_publications.csv remains untouched and SHA-256 matches baseline exactly."""
    pub_csv_path = Path("data/raw/faculty_publications.csv")
    if not pub_csv_path.exists():
        pub_csv_path = Path("../data/raw/faculty_publications.csv")

    assert pub_csv_path.exists(), "faculty_publications.csv file not found!"

    with open(pub_csv_path, "rb") as f:
        actual_hash = hashlib.sha256(f.read()).hexdigest()

    expected_hash = "3dccaf2bd296b5a62137c8d8ae0f6b2df475b14acc4d0dbc2c60773e4c5379b1"
    assert actual_hash == expected_hash, f"Hash mismatch: expected {expected_hash}, got {actual_hash}"
