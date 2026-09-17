import asyncio
import os
import sys
import uuid
from sqlalchemy import select, func, distinct
from sqlalchemy.orm import selectinload

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from app.database import async_session_factory
from app.models.user import User
from app.models.faculty import FacultyProfile, FacultyIdentifier
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.metrics import FacultyMetricSnapshot, CitationSnapshot
from app.models.review import ReviewTask
from app.services.identity_verification_service import IdentityVerificationService

async def audit():
    async with async_session_factory() as session:
        print("=" * 70)
        print("AUDIT 1: ALL 25 FACULTY IDENTITY BINDINGS")
        print("=" * 70)
        
        # 1. Total FacultyProfiles and Users
        fps = (await session.execute(select(FacultyProfile).order_by(FacultyProfile.raw_name))).scalars().all()
        users = (await session.execute(select(User))).scalars().all()
        
        print(f"Total FacultyProfiles: {len(fps)}")
        print(f"Total Users: {len(users)}")
        
        # Check 1:1 binding
        user_by_faculty_id = {u.faculty_id: u for u in users if u.faculty_id}
        unbound_fps = [fp for fp in fps if fp.id not in user_by_faculty_id]
        print(f"Unbound Faculty Profiles: {len(unbound_fps)}")
        
        orphan_users = [u for u in users if u.role == "faculty" and (not u.faculty_id or u.faculty_id not in [f.id for f in fps])]
        print(f"Orphan Faculty Users: {len(orphan_users)}")
        
        # Check for duplicate emails
        emails = [fp.institutional_email or fp.raw_email for fp in fps]
        unique_emails = set(emails)
        print(f"Faculty Emails: {len(emails)} (Unique: {len(unique_emails)})")
        
        # 2. Check Identifiers across all 25 faculty
        print("\n" + "=" * 70)
        print("AUDIT 2: EXTERNAL SCHOLARLY IDENTIFIERS ACROSS ALL FACULTY")
        print("=" * 70)
        idents = (await session.execute(select(FacultyIdentifier))).scalars().all()
        print(f"Total Faculty Identifiers in DB: {len(idents)}")
        
        # Check identifier collisions (same (type, value) on multiple distinct faculty)
        ident_map = {}
        collisions = []
        for i in idents:
            key = (i.identifier_type.lower(), i.identifier_value.strip().lower())
            if key in ident_map and ident_map[key] != i.faculty_id:
                collisions.append((key, ident_map[key], i.faculty_id))
            ident_map[key] = i.faculty_id
            
        print(f"Cross-Faculty Identifier Collisions: {len(collisions)}")
        if collisions:
            for c in collisions:
                print(f"  COLLISION: {c[0]} shared between faculty {c[1]} and {c[2]}")
                
        # 3. Check Dr. P. Siva Prasad specifically
        print("\n" + "=" * 70)
        print("AUDIT 3: DR. P. SIVA PRASAD PROFILE & INTEGRITY")
        print("=" * 70)
        siva_id = uuid.UUID("e7399ee0-758c-453b-8a96-329e3dc2cc96")
        siva_fp = (await session.execute(select(FacultyProfile).where(FacultyProfile.id == siva_id))).scalar_one_or_none()
        siva_idents = (await session.execute(select(FacultyIdentifier).where(FacultyIdentifier.faculty_id == siva_id))).scalars().all()
        
        print(f"Faculty: {siva_fp.raw_name} | Email: {siva_fp.institutional_email} | Dept: {siva_fp.department}")
        print("Identifiers:")
        for si in siva_idents:
            print(f"  - {si.identifier_type:16}: {si.identifier_value:20} (verified={si.verified}, src={si.verification_source})")
            
        # Verify OpenAlex A5003901187 is NOT attached to Siva
        has_bad_openalex = any(si.identifier_type == "openalex" and "A5003901187" in si.identifier_value for si in siva_idents)
        print(f"OpenAlex A5003901187 attached to Siva? {has_bad_openalex} (MUST BE FALSE)")
        
        # Check Siva's publications and attribution links
        siva_pas = (await session.execute(select(PublicationAuthor).where(PublicationAuthor.faculty_id == siva_id))).scalars().all()
        pub_ids = [pa.publication_id for pa in siva_pas]
        siva_pubs = (await session.execute(select(Publication).where(Publication.id.in_(pub_ids)).order_by(Publication.year.desc()))).scalars().all()
        
        print(f"\nSiva Canonical Publications Count: {len(siva_pubs)}")
        print(f"Siva PublicationAuthor Links Count: {len(siva_pas)}")
        
        # Check for duplicate publications among Siva's papers
        pub_dois = [p.doi.lower() for p in siva_pubs if p.doi]
        print(f"Distinct DOIs: {len(set(pub_dois))} of {len(pub_dois)}")
        
        total_cit_sum = sum(p.citation_count or 0 for p in siva_pubs)
        print(f"Sum of Citations: {total_cit_sum}")
        
        # Check metrics snapshot
        snap = (await session.execute(select(FacultyMetricSnapshot).where(FacultyMetricSnapshot.faculty_id == siva_id).order_by(FacultyMetricSnapshot.created_at.desc()))).scalars().first()
        if snap:
            print(f"Metrics Snapshot -> Total Pubs: {snap.total_publications}, Citations: {snap.total_citations}, h-index: {snap.h_index}, i10-index: {snap.i10_index}")

        # 4. Check Global Orphan records
        print("\n" + "=" * 70)
        print("AUDIT 4: GLOBAL ORPHAN RECORD AUDIT")
        print("=" * 70)
        total_pubs = (await session.execute(select(func.count(Publication.id)))).scalar_one()
        total_sources = (await session.execute(select(func.count(PublicationSource.id)))).scalar_one()
        total_pas = (await session.execute(select(func.count(PublicationAuthor.id)))).scalar_one()
        
        # Check orphan PublicationAuthor (missing publication or faculty)
        orphan_pa_pub = (await session.execute(
            select(func.count(PublicationAuthor.id))
            .outerjoin(Publication, PublicationAuthor.publication_id == Publication.id)
            .where(Publication.id == None)
        )).scalar_one()
        
        orphan_pa_fac = (await session.execute(
            select(func.count(PublicationAuthor.id))
            .outerjoin(FacultyProfile, PublicationAuthor.faculty_id == FacultyProfile.id)
            .where(FacultyProfile.id == None)
        )).scalar_one()
        
        # Check orphan PublicationSource (missing publication)
        orphan_ps = (await session.execute(
            select(func.count(PublicationSource.id))
            .outerjoin(Publication, PublicationSource.publication_id == Publication.id)
            .where(Publication.id == None)
        )).scalar_one()
        
        print(f"Total Canonical Publications: {total_pubs}")
        print(f"Total Publication Sources: {total_sources}")
        print(f"Total Publication Authors: {total_pas}")
        print(f"Orphan PublicationAuthor (no pub): {orphan_pa_pub}")
        print(f"Orphan PublicationAuthor (no faculty): {orphan_pa_fac}")
        print(f"Orphan PublicationSource (no pub): {orphan_ps}")

        # 5. Test Status Semantics via Service
        print("\n" + "=" * 70)
        print("AUDIT 5: STATUS SEMANTICS API RETURN FOR SIVA")
        print("=" * 70)
        service = IdentityVerificationService(session)
        status_res = await service.get_faculty_identifiers_status(siva_id)
        for ident_item in status_res["identifiers"]:
            print(f"Source: {ident_item['type']:16} | Identity: {ident_item['identity_status']:12} | Ingestion: {ident_item['ingestion_status']:23} | Live API: {ident_item['live_api_status']}")

if __name__ == "__main__":
    asyncio.run(audit())
