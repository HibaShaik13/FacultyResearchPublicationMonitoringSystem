import asyncio
import json
import logging
import sys
import uuid
from typing import Dict, Any
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
import httpx

# Force utf-8 stdout
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from app.database import async_session_factory
from app.models.faculty import FacultyProfile, FacultyIdentifier, FacultyNameVariant
from app.models.user import User
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.metrics import FacultyMetricSnapshot, CitationSnapshot
from app.core.security import hash_password
from app.agents.identity_agent import FacultyIdentityAgent
from app.agents.discovery_agent import PublicationDiscoveryAgent
from app.agents.attribution_agent import FacultyAttributionAgent
from app.agents.metrics_agent import MetricsAgent
from app.main import app

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("add_faculty")

async def add_and_sync_faculty():
    print("===================================================================")
    print("STEP 1: CREATING FACULTY PROFILE FOR DR. P. SIVA PRASAD")
    print("===================================================================")
    
    async with async_session_factory() as session:
        # Check if already exists
        stmt = select(FacultyProfile).where(
            (FacultyProfile.institutional_email == "drpsp_cse@vignan.ac.in") |
            (FacultyProfile.normalized_name == "p. siva prasad")
        )
        res = await session.execute(stmt)
        existing_profile = res.scalars().first()

        if existing_profile:
            faculty_id = existing_profile.id
            print(f"Faculty profile already exists: {existing_profile.raw_name} (ID: {faculty_id})")
        else:
            faculty_id = uuid.uuid4()
            profile = FacultyProfile(
                id=faculty_id,
                raw_name="Dr P. Siva Prasad",
                raw_designation="Associate Professor",
                raw_email="drpsp_cse@vignan.ac.in",
                raw_phone="8309646690",
                normalized_name="p. siva prasad",
                first_name="P.",
                last_name="Siva Prasad",
                title_prefix="Dr",
                department="CSE",
                designation="Associate Professor",
                institutional_email="drpsp_cse@vignan.ac.in",
                phone="8309646690",
                research_interests=["Algebra", "Machine Learning", "Deep learning", "Cryptography"],
                teaching_engagements="22 years of teaching experience",
                education={"raw": "Mathematics | November 2015"},
                academic_experience=None,
                awards=None,
                memberships=None,
                research_summary=None,
                administrative_positions="Board of Academic Member — February 2017 | Academic Counsel Member — June 2021",
                events=None,
                csv_row_hash=None,
                source_file="manual_profile_addition",
                declared_publication_count=None,
                status="active"
            )
            session.add(profile)
            
            # Name variants
            variants = [
                "p. siva prasad",
                "p siva prasad",
                "siva prasad p",
                "siva prasad p.",
                "sivaprasad p",
                "p. sivaprasad",
                "dr p. siva prasad",
                "dr. p. siva prasad",
                "dr p siva prasad",
                "p. s. prasad"
            ]
            for var in variants:
                nv = FacultyNameVariant(
                    id=uuid.uuid4(),
                    faculty_id=faculty_id,
                    name_variant=var,
                    variant_source="profile_creation",
                    is_confirmed=True
                )
                session.add(nv)

            # User record for authentication
            user_stmt = select(User).where(func.lower(User.email) == "drpsp_cse@vignan.ac.in")
            user_res = await session.execute(user_stmt)
            if not user_res.scalars().first():
                new_user = User(
                    id=uuid.uuid4(),
                    email="drpsp_cse@vignan.ac.in",
                    password_hash=hash_password("faculty123"),
                    full_name="Dr P. Siva Prasad",
                    role="faculty",
                    faculty_id=faculty_id,
                    is_active=True
                )
                session.add(new_user)

            await session.commit()
            print(f"Created new FacultyProfile for Dr P. Siva Prasad (ID: {faculty_id})")

    print("\n===================================================================")
    print("STEP 2: RUNNING SCHOLARLY IDENTITY RESOLUTION (Agent 1)")
    print("===================================================================")
    async with async_session_factory() as session:
        identity_agent = FacultyIdentityAgent(session)
        id_stats = await identity_agent.run()
        print("IdentityAgent stats:", json.dumps(id_stats, indent=2, default=str))

    print("\n===================================================================")
    print("STEP 3: RUNNING REAL PUBLICATION DISCOVERY (Agent 4)")
    print("===================================================================")
    async with async_session_factory() as session:
        discovery_agent = PublicationDiscoveryAgent(session)
        disc_stats = await discovery_agent.run()
        print("PublicationDiscoveryAgent stats:", json.dumps(disc_stats, indent=2, default=str))

    print("\n===================================================================")
    print("STEP 4: RUNNING FACULTY ATTRIBUTION (Agent 6)")
    print("===================================================================")
    async with async_session_factory() as session:
        attribution_agent = FacultyAttributionAgent(session)
        attr_stats = await attribution_agent.run()
        print("FacultyAttributionAgent stats:", json.dumps(attr_stats, indent=2, default=str))

    print("\n===================================================================")
    print("STEP 5: RUNNING CITATION ENRICHMENT & METRICS COMPUTATION (Agent 9)")
    print("===================================================================")
    async with async_session_factory() as session:
        metrics_agent = MetricsAgent(session)
        metrics_stats = await metrics_agent.run()
        print("MetricsAgent stats:", json.dumps(metrics_stats, indent=2, default=str))

    print("\n===================================================================")
    print("STEP 6: READ-ONLY VERIFICATION OF DR. P. SIVA PRASAD")
    print("===================================================================")
    async with async_session_factory() as session:
        stmt = (
            select(FacultyProfile)
            .options(
                selectinload(FacultyProfile.identifiers),
                selectinload(FacultyProfile.name_variants),
                selectinload(FacultyProfile.metric_snapshots),
                selectinload(FacultyProfile.publication_links).selectinload(PublicationAuthor.publication),
            )
            .where(FacultyProfile.id == faculty_id)
        )
        res = await session.execute(stmt)
        fac = res.scalars().first()

        print(f"Faculty: {fac.raw_name} ({fac.id})")
        print(f"Department: {fac.department}, Designation: {fac.designation}")
        print(f"Email: {fac.institutional_email}, Phone: {fac.phone}")
        print(f"Research Interests: {fac.research_interests}")
        print(f"Education: {fac.education}")
        print(f"Teaching: {fac.teaching_engagements}")
        print(f"Administrative: {fac.administrative_positions}")
        
        print("\nIdentifiers:")
        for ident in fac.identifiers:
            print(f"  - [{ident.identifier_type}] {ident.identifier_value} (conf={ident.confidence}, verified={ident.verified})")

        print(f"\nAttributed Publications ({len(fac.publication_links)}):")
        for link in fac.publication_links[:10]:
            p = link.publication
            if p:
                print(f"  * [{p.citation_source or 'none'}: {p.citation_count} cits, conf={link.attribution_confidence}] {p.title[:65]} (DOI: {p.doi or 'None'})")

        print("\nMetric Snapshots:")
        for s in fac.metric_snapshots:
            print(f"  - [{s.snapshot_date}] Total Pubs: {s.total_publications}, Total Cits: {s.total_citations}, h-index: {s.h_index}, i10-index: {s.i10_index}")

    print("\n===================================================================")
    print("STEP 7: API VERIFICATION VIA ASGI HTTP CLIENT")
    print("===================================================================")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Faculty profile
        f_resp = await client.get(f"/api/v1/faculty/{faculty_id}")
        print(f"GET /api/v1/faculty/{faculty_id} -> Status: {f_resp.status_code}")
        print("Faculty Response:", json.dumps(f_resp.json(), indent=2))

        # 2. Analytics dashboard
        d_resp = await client.get(f"/api/v1/analytics/dashboard?faculty_id={faculty_id}")
        print(f"\nGET /api/v1/analytics/dashboard?faculty_id={faculty_id} -> Status: {d_resp.status_code}")
        print("Dashboard Response:", json.dumps(d_resp.json(), indent=2))

        # 3. Publications filtered
        p_resp = await client.get(f"/api/v1/publications/?faculty_id={faculty_id}")
        print(f"\nGET /api/v1/publications/?faculty_id={faculty_id} -> Total: {p_resp.json().get('total')}")

        # 4. Publication stats overall
        s_resp = await client.get("/api/v1/publications/stats")
        print(f"\nGET /api/v1/publications/stats -> Status: {s_resp.status_code}")
        print("Overall Stats:", json.dumps(s_resp.json(), indent=2))

if __name__ == "__main__":
    asyncio.run(add_and_sync_faculty())
