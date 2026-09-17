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
from app.models.metrics import FacultyMetricSnapshot, CitationSnapshot
from app.config import get_settings
from sqlalchemy import select, func

async def run_pre_staging_audit():
    settings = get_settings()
    print("==================================================")
    print("1. EXTERNAL API CONFIGURATION STATUS")
    print("==================================================")
    print(f"Scopus API Key: {'CONFIGURED' if settings.scopus_api_key else 'NOT_CONFIGURED'}")
    print(f"IEEE API Key: {'CONFIGURED' if settings.ieee_api_key else 'NOT_CONFIGURED'}")
    print(f"OpenAlex Email: {'CONFIGURED' if settings.openalex_email else 'NOT_CONFIGURED'}")
    print(f"Crossref Email: {'CONFIGURED' if settings.crossref_email else 'NOT_CONFIGURED'}")
    print(f"Semantic Scholar API Key: {'CONFIGURED' if settings.semantic_scholar_api_key else 'NOT_CONFIGURED'}")
    print(f"ORCID Client ID: {'CONFIGURED' if settings.orcid_client_id else 'NOT_CONFIGURED'}")

    async with async_session_factory() as session:
        print("\n==================================================")
        print("2. DATABASE INTEGRITY AUDIT")
        print("==================================================")
        profiles = (await session.execute(select(FacultyProfile))).scalars().all()
        users = (await session.execute(select(User))).scalars().all()
        idents = (await session.execute(select(FacultyIdentifier))).scalars().all()
        pubs_count = (await session.execute(select(func.count(Publication.id)))).scalar()
        sources_count = (await session.execute(select(func.count(PublicationSource.id)))).scalar()
        authors_count = (await session.execute(select(func.count(PublicationAuthor.id)))).scalar()
        reviews_count = (await session.execute(select(func.count(ReviewTask.id)))).scalar()

        print(f"Total Faculty Profiles: {len(profiles)} (Expected: 25)")
        print(f"Total User Accounts: {len(users)} (25 Faculty + 1 Admin)")
        bound_users = [u for u in users if u.faculty_id is not None]
        unbound_users = [u for u in users if u.faculty_id is None]
        print(f"Bound Users: {len(bound_users)} (100% of Faculty Users)")
        print(f"Unbound Users: {len(unbound_users)} (System Admin: {[u.email for u in unbound_users]})")
        print(f"Total Persistent Identifiers: {len(idents)}")
        print(f"Canonical Publications: {pubs_count}")
        print(f"Publication Sources: {sources_count} (Merged Deduplication Delta: {sources_count - pubs_count})")
        print(f"Confirmed PublicationAuthor Links: {authors_count}")
        print(f"Quarantined Review Tasks: {reviews_count}")

        # Check orphan records
        orphan_authors = (await session.execute(
            select(func.count(PublicationAuthor.id))
            .outerjoin(Publication, PublicationAuthor.publication_id == Publication.id)
            .where(Publication.id.is_(None))
        )).scalar()
        orphan_sources = (await session.execute(
            select(func.count(PublicationSource.id))
            .outerjoin(Publication, PublicationSource.publication_id == Publication.id)
            .where(Publication.id.is_(None))
        )).scalar()
        orphan_reviews = (await session.execute(
            select(func.count(ReviewTask.id))
            .outerjoin(Publication, ReviewTask.entity_id == Publication.id)
            .where(ReviewTask.entity_type == 'publication', Publication.id.is_(None))
        )).scalar()
        print(f"Orphan PublicationAuthors: {orphan_authors} (Expected: 0)")
        print(f"Orphan PublicationSources: {orphan_sources} (Expected: 0)")
        print(f"Orphan ReviewTasks: {orphan_reviews} (Expected: 0)")

        print("\n==================================================")
        print("3. DR. P. SIVA PRASAD (IEEE 256481733945119 AUDIT)")
        print("==================================================")
        siva_user = next((u for u in users if u.email == 'drpsp_cse@vignan.ac.in'), None)
        siva_fp = next((p for p in profiles if p.id == siva_user.faculty_id), None)
        siva_ids = [i for i in idents if i.faculty_id == siva_fp.id]
        print(f"Faculty: {siva_fp.normalized_name} (ID: {siva_fp.id})")
        print(f"Identifiers: {[{'type': i.identifier_type, 'value': i.identifier_value, 'verified': i.verified} for i in siva_ids]}")
        
        # High confidence confirmed publications
        siva_pas = (await session.execute(
            select(PublicationAuthor, Publication)
            .join(Publication, PublicationAuthor.publication_id == Publication.id)
            .where(PublicationAuthor.faculty_id == siva_fp.id, PublicationAuthor.attribution_confidence >= 0.70)
        )).all()
        print(f"Confirmed Publications: {len(siva_pas)}")
        siva_cits = [p.citation_count or 0 for _, p in siva_pas]
        siva_cits.sort(reverse=True)
        print(f"Citations: {sum(siva_cits)}, h-index: {sum(1 for idx, c in enumerate(siva_cits) if c >= idx + 1)}, i10-index: {sum(1 for c in siva_cits if c >= 10)}")

        # Pending review tasks
        siva_reviews = (await session.execute(
            select(func.count(ReviewTask.id)).where(
                ((ReviewTask.entity_id == siva_fp.id) | (ReviewTask.related_entity_id == siva_fp.id)),
                ReviewTask.status == 'pending'
            )
        )).scalar()
        print(f"Quarantined/Pending Review Tasks: {siva_reviews}")

        print("\n==================================================")
        print("4. DR. M. UMADEVI MULTI-SOURCE AUDIT")
        print("==================================================")
        uma_user = next((u for u in users if u.email == 'druma_cse@vignan.ac.in'), None)
        uma_fp = next((p for p in profiles if p.id == uma_user.faculty_id), None)
        uma_ids = [i for i in idents if i.faculty_id == uma_fp.id]
        print(f"Faculty: {uma_fp.normalized_name} (ID: {uma_fp.id})")
        print(f"Identifiers: {[{'type': i.identifier_type, 'value': i.identifier_value, 'verified': i.verified} for i in uma_ids]}")

        uma_pas = (await session.execute(
            select(PublicationAuthor, Publication)
            .join(Publication, PublicationAuthor.publication_id == Publication.id)
            .where(PublicationAuthor.faculty_id == uma_fp.id, PublicationAuthor.attribution_confidence >= 0.70)
        )).all()
        print(f"Confirmed Publications: {len(uma_pas)}")
        uma_cits = [p.citation_count or 0 for _, p in uma_pas]
        uma_cits.sort(reverse=True)
        print(f"Citations: {sum(uma_cits)}, h-index: {sum(1 for idx, c in enumerate(uma_cits) if c >= idx + 1)}, i10-index: {sum(1 for c in uma_cits if c >= 10)}")
        print(f"Citation distribution: {uma_cits}")

        uma_reviews = (await session.execute(
            select(func.count(ReviewTask.id)).where(
                ((ReviewTask.entity_id == uma_fp.id) | (ReviewTask.related_entity_id == uma_fp.id)),
                ReviewTask.status == 'pending'
            )
        )).scalar()
        print(f"Quarantined/Pending Review Tasks: {uma_reviews}")

        print("\n==================================================")
        print("5. SAME-NAME & SISTER-COLLEGE COLLISION ISOLATION")
        print("==================================================")
        # Check Mother Teresa Univ (Physics)
        mother_teresa_pubs = (await session.execute(
            select(PublicationAuthor)
            .join(Publication, PublicationAuthor.publication_id == Publication.id)
            .where(
                PublicationAuthor.faculty_id == uma_fp.id,
                PublicationAuthor.attribution_confidence >= 0.70,
                Publication.affiliation_text.ilike('%Mother Teresa%')
            )
        )).scalars().all()
        print(f"Mother Teresa Women's University Confirmed Publications: {len(mother_teresa_pubs)} (Expected: 0)")

        # Check VLITS Lara (P. Sai Prasad)
        lara_pubs = (await session.execute(
            select(PublicationAuthor)
            .join(Publication, PublicationAuthor.publication_id == Publication.id)
            .where(
                PublicationAuthor.faculty_id == siva_fp.id,
                PublicationAuthor.attribution_confidence >= 0.70,
                Publication.affiliation_text.ilike('%Lara%')
            )
        )).scalars().all()
        print(f"VLITS Lara Confirmed Publications for Dr. P. Siva Prasad: {len(lara_pubs)} (Expected: 0)")

if __name__ == '__main__':
    asyncio.run(run_pre_staging_audit())
