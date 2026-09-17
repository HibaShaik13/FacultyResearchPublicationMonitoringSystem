import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database import async_session_factory
from app.models.faculty import FacultyProfile, FacultyIdentifier
from app.models.user import User
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.review import ReviewTask
from app.services.identity_verification_service import IdentityVerificationService
from sqlalchemy import select, func

async def run_uat():
    async with async_session_factory() as session:
        print("=== UAT 1: FACULTY COUNTS & BINDING AUDIT ===")
        total_profiles = (await session.execute(select(func.count(FacultyProfile.id)))).scalar()
        total_users = (await session.execute(select(func.count(User.id)))).scalar()
        bound_users = (await session.execute(select(func.count(User.id)).where(User.faculty_id.isnot(None)))).scalar()
        unbound_users = (await session.execute(select(func.count(User.id)).where(User.faculty_id.is_(None)))).scalar()
        print(f"Total Faculty Profiles: {total_profiles}")
        print(f"Total Users: {total_users}")
        print(f"Bound Users: {bound_users}")
        print(f"Unbound Users: {unbound_users} (admin accounts)")

        print("\n=== UAT 2: DR. P. SIVA PRASAD PROFILE & METRICS ===")
        siva_user = (await session.execute(select(User).where(User.email == 'drpsp_cse@vignan.ac.in'))).scalar_one_or_none()
        siva_fp = (await session.execute(select(FacultyProfile).where(FacultyProfile.id == siva_user.faculty_id))).scalar_one_or_none()
        print(f"User ID: {siva_user.id} -> bound faculty_id: {siva_user.faculty_id}")
        print(f"FacultyProfile: {siva_fp.normalized_name}, Dept: {siva_fp.department}, Email: {siva_fp.institutional_email}")
        
        siva_ids = (await session.execute(select(FacultyIdentifier).where(FacultyIdentifier.faculty_id == siva_fp.id))).scalars().all()
        print(f"Identifiers: {[{'type': i.identifier_type, 'value': i.identifier_value, 'verified': i.verified} for i in siva_ids]}")
        
        # Calculate Siva's exact metrics from confirmed PublicationAuthor records
        siva_pas = (await session.execute(
            select(PublicationAuthor, Publication)
            .join(Publication, PublicationAuthor.publication_id == Publication.id)
            .where(PublicationAuthor.faculty_id == siva_fp.id, PublicationAuthor.attribution_confidence >= 0.70)
        )).all()
        print(f"Confirmed Publications Count: {len(siva_pas)}")
        citations = [p.citation_count or 0 for _, p in siva_pas]
        citations.sort(reverse=True)
        total_citations = sum(citations)
        h_index = sum(1 for idx, c in enumerate(citations) if c >= idx + 1)
        i10_index = sum(1 for c in citations if c >= 10)
        print(f"Metrics Proof: Citations={total_citations}, h-index={h_index}, i10-index={i10_index}")
        print(f"Citation distribution: {citations}")

        siva_pending = (await session.execute(
            select(func.count(ReviewTask.id)).where(
                ((ReviewTask.entity_id == siva_fp.id) | (ReviewTask.related_entity_id == siva_fp.id)),
                ReviewTask.status == 'pending'
            )
        )).scalar()
        print(f"Pending Attribution Review Tasks: {siva_pending}")

        print("\n=== UAT 3: DR. M. UMADEVI PROFILE & METRICS ===")
        uma_user = (await session.execute(select(User).where(User.email == 'druma_cse@vignan.ac.in'))).scalar_one_or_none()
        uma_fp = (await session.execute(select(FacultyProfile).where(FacultyProfile.id == uma_user.faculty_id))).scalar_one_or_none()
        print(f"User ID: {uma_user.id} -> bound faculty_id: {uma_user.faculty_id}")
        print(f"FacultyProfile: {uma_fp.normalized_name}, Dept: {uma_fp.department}, Email: {uma_fp.institutional_email}")
        
        uma_ids = (await session.execute(select(FacultyIdentifier).where(FacultyIdentifier.faculty_id == uma_fp.id))).scalars().all()
        print(f"Identifiers: {[{'type': i.identifier_type, 'value': i.identifier_value, 'verified': i.verified} for i in uma_ids]}")
        
        uma_pas = (await session.execute(
            select(PublicationAuthor, Publication)
            .join(Publication, PublicationAuthor.publication_id == Publication.id)
            .where(PublicationAuthor.faculty_id == uma_fp.id, PublicationAuthor.attribution_confidence >= 0.70)
        )).all()
        print(f"Confirmed Publications Count: {len(uma_pas)}")
        uma_cits = [p.citation_count or 0 for _, p in uma_pas]
        uma_cits.sort(reverse=True)
        uma_tot_cit = sum(uma_cits)
        uma_h = sum(1 for idx, c in enumerate(uma_cits) if c >= idx + 1)
        uma_i10 = sum(1 for c in uma_cits if c >= 10)
        print(f"Metrics Proof: Citations={uma_tot_cit}, h-index={uma_h}, i10-index={uma_i10}")
        print(f"Citation distribution: {uma_cits}")

        uma_pending = (await session.execute(
            select(func.count(ReviewTask.id)).where(
                ((ReviewTask.entity_id == uma_fp.id) | (ReviewTask.related_entity_id == uma_fp.id)),
                ReviewTask.status == 'pending'
            )
        )).scalar()
        print(f"Pending Attribution Review Tasks: {uma_pending}")

        print("\n=== UAT 4: SAME-NAME COLLISION TEST (Mother Teresa Women's University, Dept of Physics) ===")
        # Check if any publications with 'Mother Teresa Women' or 'Physics' are confirmed to Dr. M. Umadevi (CSE)
        physics_pubs = (await session.execute(
            select(PublicationAuthor, Publication)
            .join(Publication, PublicationAuthor.publication_id == Publication.id)
            .where(
                PublicationAuthor.faculty_id == uma_fp.id,
                PublicationAuthor.attribution_confidence >= 0.70,
                Publication.affiliation_text.ilike('%Mother Teresa%')
            )
        )).all()
        print(f"Erroneous Physics/Mother Teresa confirmed pubs: {len(physics_pubs)} (Expected: 0)")
        
        print("\n=== UAT 5: PUBLICATION LINK AND DOI VERIFICATION ===")
        # Check sample confirmed publications for Umadevi to verify valid DOI and source_url
        for pa, pub in uma_pas[:5]:
            doi_link = f"https://doi.org/{pub.doi}" if pub.doi else "NO_DOI"
            print(f"- Pub: {pub.title[:50]}... | DOI: {doi_link} | Conf: {pa.attribution_confidence}")

if __name__ == '__main__':
    asyncio.run(run_uat())
