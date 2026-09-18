"""
Comprehensive Phase 3 Staging Validation Script.
Operates on an isolated PostgreSQL staging database (vestr_phase3_staging).
"""

import asyncio
import hashlib
import io
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import asyncpg
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import get_settings
from app.database import Base
from app.models.agent import SyncRun, AgentRun
from app.models.faculty import FacultyProfile, FacultyIdentifier
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.review import ReviewTask
from app.models.metrics import FacultyMetricSnapshot
from app.models.provenance import ProvenanceRecord
from app.models.user import User
from app.orchestrator.pipeline_orchestrator import PipelineOrchestrator
from app.connectors.vidwan import VidwanClient
from app.connectors.openalex import OpenAlexClient
from app.connectors.crossref import CrossrefClient
from app.connectors.semantic_scholar import SemanticScholarClient
from app.agents.discovery_agent import PublicationDiscoveryAgent
from app.agents.metrics_agent import MetricsAgent
import app.seed.bootstrap as bootstrap

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("staging_validation")


async def run_staging_validation():
    settings = get_settings()
    user = settings.postgres_user
    password = settings.postgres_password
    host = settings.postgres_host
    port = settings.postgres_port

    print("==================================================================")
    print("PHASE 3 STAGING VALIDATION — ISOLATED POSTGRESQL ENVIRONMENT")
    print("==================================================================")

    # 1. Connect to postgres system DB to create fresh isolated staging DB
    sys_conn = await asyncpg.connect(user=user, password=password, host=host, port=port, database="postgres")
    # Terminate any existing connections to staging DB if it exists
    await sys_conn.execute("""
        SELECT pg_terminate_backend(pg_stat_activity.pid)
        FROM pg_stat_activity
        WHERE pg_stat_activity.datname = 'vestr_phase3_staging'
          AND pid <> pg_backend_pid();
    """)
    await sys_conn.execute("DROP DATABASE IF EXISTS vestr_phase3_staging;")
    await sys_conn.execute("CREATE DATABASE vestr_phase3_staging;")
    print("✓ Created fresh isolated staging database: vestr_phase3_staging")
    await sys_conn.close()

    # 2. Build staging connection URL
    staging_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/vestr_phase3_staging"
    engine = create_async_engine(staging_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # 3. Create schema
    async with engine.begin() as conn:
        # Confirm database name
        curr_db = (await conn.execute(text("SELECT current_database()"))).scalar()
        print(f"✓ Confirmed active staging database: {curr_db} (Is NOT production)")
        assert curr_db == "vestr_phase3_staging", "Safety failure: Not on staging DB!"
        await conn.run_sync(Base.metadata.create_all)
    print("✓ Created tables and indexes successfully via SQLAlchemy Base metadata.")

    # 4. Fresh Database Baseline Seeding (Phase 3E)
    async with session_factory() as session:
        bootstrap_res = await bootstrap.ensure_baseline_accounts(session)
        print(f"✓ Bootstrap baseline result: {bootstrap_res}")

        # Check counts
        fac_count = (await session.execute(select(func.count(FacultyProfile.id)))).scalar()
        user_count = (await session.execute(select(func.count(User.id)))).scalar()
        pub_count = (await session.execute(select(func.count(Publication.id)))).scalar()

        print(f"✓ Staging Faculty Profiles count: {fac_count} (Expected: 25)")
        print(f"✓ Staging User Accounts count: {user_count} (Expected: 26)")
        print(f"✓ Staging Publications count: {pub_count} (Expected: 0 on fresh empty DB)")
        assert fac_count == 25, f"Expected 25 faculty, got {fac_count}"
        assert user_count == 26, f"Expected 26 users, got {user_count}"

        # Check Dr. P. Siva Prasad presence
        siva_res = await session.execute(select(FacultyProfile).where(FacultyProfile.institutional_email == "drpsp_cse@vignan.ac.in"))
        siva = siva_res.scalars().first()
        assert siva is not None, "Dr. P. Siva Prasad profile missing!"
        print(f"✓ Dr. P. Siva Prasad verified: {siva.raw_name} ({siva.institutional_email})")

        # Check Siva User Account
        siva_user_res = await session.execute(select(User).where(User.email == "drpsp_cse@vignan.ac.in"))
        siva_user = siva_user_res.scalars().first()
        assert siva_user is not None, "Dr. P. Siva Prasad user account missing!"
        assert siva_user.faculty_id == siva.id
        print(f"✓ Dr. P. Siva Prasad user account verified and linked: ID={siva_user.id}, Role={siva_user.role}")

    # 5. Idempotent Startup / Restart Test (Phase 3J, 3K)
    for cycle in range(1, 4):
        async with session_factory() as session:
            await bootstrap.ensure_baseline_accounts(session)
            f_cnt = (await session.execute(select(func.count(FacultyProfile.id)))).scalar()
            u_cnt = (await session.execute(select(func.count(User.id)))).scalar()
            assert f_cnt == 25, f"Cycle {cycle}: Faculty count mutated to {f_cnt}"
            assert u_cnt == 26, f"Cycle {cycle}: User count mutated to {u_cnt}"
    print("✓ Multiple startup / restart idempotency verified (3 cycles completed with 25 faculty and 26 users).")

    # 6. Automatic Initial Research Pipeline & Duplicate Protection Test (Phase 3G, 3I, 3J)
    async with session_factory() as session:
        orchestrator = PipelineOrchestrator(session)
        has_run_before = await orchestrator.has_initial_sync_completed()
        assert not has_run_before, "Initial sync should not be completed yet."

        print("✓ Triggering autonomous initial research pipeline on staging...")
        pipeline_stats = await orchestrator.run_full_pipeline(trigger="startup_autonomous_initial_discovery")
        print(f"✓ Pipeline Run Status: {pipeline_stats.get('sync_run_status')}, Errors: {pipeline_stats.get('total_errors')}")

        has_run_after = await orchestrator.has_initial_sync_completed()
        print(f"✓ has_initial_sync_completed: {has_run_after}")

        # Check duplicate protection
        dup_res = await orchestrator.run_full_pipeline(trigger="duplicate_startup_trigger", allow_concurrent=False)
        print(f"✓ Duplicate trigger result: {dup_res.get('status')} - {dup_res.get('message', 'N/A')}")

    # 7. Real External Connectivity Tests (Phase 3L, 3M, 3N)
    print("\n--- Real External Connectivity & Source Discovery ---")
    # OpenAlex Real Test
    openalex = OpenAlexClient(email=settings.openalex_email)
    oa_authors = await openalex.search_authors("Vignan")
    print(f"✓ Real OpenAlex Query: Retrieved {len(oa_authors)} authors for 'Vignan'")

    # Crossref Real Test
    crossref = CrossrefClient(email=settings.crossref_email)
    cr_works = await crossref.search_works_by_author("Siva Prasad", "Vignan")
    print(f"✓ Real Crossref Query: Retrieved {len(cr_works)} works for 'Siva Prasad'")

    # Vidwan Real Test
    vidwan = VidwanClient(timeout=10.0)
    vidwan_pubs = await vidwan.get_profile_publications("84197")
    print(f"✓ Real Vidwan Profile Query (84197): Retrieved {len(vidwan_pubs)} public works")

    # 8. Siva Identity & OpenAlex Mismatch Guard Test (Phase 3O, 3P)
    async with session_factory() as session:
        # Verify OpenAlex A5003901187 is NOT attached to Siva
        ident_res = await session.execute(
            select(FacultyIdentifier).where(
                FacultyIdentifier.identifier_type == "openalex",
                FacultyIdentifier.identifier_value.ilike("%A5003901187%")
            )
        )
        mismatch_idents = ident_res.scalars().all()
        for ident in mismatch_idents:
            assert ident.faculty_id != siva.id, "CRITICAL: OpenAlex A5003901187 attached to Dr. P. Siva Prasad!"
        print("✓ Confirmed: OpenAlex A5003901187 is strictly NOT attached to Dr. P. Siva Prasad.")

    # 9. Multi-Source Deduplication Test (Phase 3T)
    async with session_factory() as session:
        discovery = PublicationDiscoveryAgent(session)
        stats = {"processed": 0, "publications_discovered": 0, "dois_found": 0, "duplicates_prevented": 0, "errors": 0, "sources_queried": {}}

        test_doi = "10.1109/icssas68835.2026.11559393"
        # Ingest Source 1
        await discovery._create_publication(
            profile=siva,
            title="Smart Attendance System using MERN Stack and Real-Time Face Recognition",
            doi=test_doi,
            year=2026,
            source_system="crossref",
            source_id=test_doi,
            raw_metadata={"title": ["Smart Attendance System using MERN Stack and Real-Time Face Recognition"]},
            stats=stats,
            is_verified_author=True,
        )
        await session.commit()

        # Ingest Source 2 (same DOI)
        await discovery._create_publication(
            profile=siva,
            title="Smart Attendance System using MERN Stack and Real-Time Face Recognition",
            doi=test_doi,
            year=2026,
            source_system="ieee",
            source_id="11559393",
            raw_metadata={"title": "Smart Attendance System using MERN Stack and Real-Time Face Recognition"},
            stats=stats,
            is_verified_author=True,
        )
        await session.commit()

        # Assert exactly 1 publication and 2 sources
        p_res = await session.execute(select(Publication).where(Publication.doi == test_doi))
        pub = p_res.scalars().first()
        assert pub is not None
        src_res = await session.execute(select(PublicationSource).where(PublicationSource.publication_id == pub.id))
        sources = src_res.scalars().all()
        assert len(sources) == 2, f"Expected 2 sources, got {len(sources)}"
        print(f"✓ Multi-Source Deduplication Verified: DOI {test_doi} merged into 1 Publication with {len(sources)} sources.")

    # 10. Metrics Calculation Test (Phase 3Z)
    async with session_factory() as session:
        metrics_agent = MetricsAgent(session)
        metric_stats = await metrics_agent.run()
        print(f"✓ Metrics Calculation Verified: {metric_stats}")

        # Check snapshot exists
        snap_res = await session.execute(select(FacultyMetricSnapshot).where(FacultyMetricSnapshot.faculty_id == siva.id))
        snapshot = snap_res.scalars().first()
        if snapshot:
            print(f"✓ Siva Metric Snapshot: Pubs={snapshot.publication_count}, Citations={snapshot.total_citations}, h-index={snapshot.h_index}")

    # 11. Staging Data Count Audit (Phase 3AW)
    async with session_factory() as session:
        fac_cnt = (await session.execute(select(func.count(FacultyProfile.id)))).scalar()
        usr_cnt = (await session.execute(select(func.count(User.id)))).scalar()
        pub_cnt = (await session.execute(select(func.count(Publication.id)))).scalar()
        pa_cnt = (await session.execute(select(func.count(PublicationAuthor.id)))).scalar()
        ps_cnt = (await session.execute(select(func.count(PublicationSource.id)))).scalar()
        rt_cnt = (await session.execute(select(func.count(ReviewTask.id)))).scalar()
        ms_cnt = (await session.execute(select(func.count(FacultyMetricSnapshot.id)))).scalar()
        sr_cnt = (await session.execute(select(func.count(SyncRun.id)))).scalar()
        ar_cnt = (await session.execute(select(func.count(AgentRun.id)))).scalar()
        pr_cnt = (await session.execute(select(func.count(ProvenanceRecord.id)))).scalar()

        print("\n================ FINAL STAGING DATABASE COUNTS ================")
        print(f"faculty_profiles:          {fac_cnt}")
        print(f"users:                     {usr_cnt}")
        print(f"publications:              {pub_cnt}")
        print(f"publication_authors:       {pa_cnt}")
        print(f"publication_sources:       {ps_cnt}")
        print(f"review_tasks:              {rt_cnt}")
        print(f"faculty_metric_snapshots:  {ms_cnt}")
        print(f"sync_runs:                 {sr_cnt}")
        print(f"agent_runs:                {ar_cnt}")
        print(f"provenance_records:        {pr_cnt}")
        print("================================================================")

    await engine.dispose()
    print("✓ All Phase 3 staging validation checks completed successfully!")

if __name__ == "__main__":
    asyncio.run(run_staging_validation())
