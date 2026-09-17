import asyncio
import json
import os
import sys
import time
import urllib.request
import urllib.parse
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.database import async_session_factory
from app.models.faculty import FacultyProfile, FacultyIdentifier
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from sqlalchemy import select, func

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

async def audit():
    async with async_session_factory() as session:
        # 1. Faculty details
        fp_res = await session.execute(select(FacultyProfile).where(FacultyProfile.id == 'e7399ee0-758c-453b-8a96-329e3dc2cc96'))
        fp = fp_res.scalar_one_or_none()
        print(f"FACULTY PROFILE: {fp.first_name} {fp.last_name}, Dept: {fp.department}, Email: {fp.institutional_email}")

        # 2. Identifiers
        id_res = await session.execute(select(FacultyIdentifier).where(FacultyIdentifier.faculty_id == fp.id))
        idents = id_res.scalars().all()
        print("\n=== IDENTIFIERS IN DB ===")
        for i in idents:
            print(f"Type: {i.identifier_type:15} | Value: {i.identifier_value:20} | Verified: {i.verified} | Details: {i.verification_source}")

        # 3. Publications
        p_res = await session.execute(
            select(Publication, PublicationAuthor)
            .join(PublicationAuthor, PublicationAuthor.publication_id == Publication.id)
            .where(PublicationAuthor.faculty_id == fp.id)
            .order_by(Publication.year.desc())
        )
        pubs = p_res.all()
        print(f"\n=== SIVA CONFIRMED PUBLICATIONS ({len(pubs)}) ===")
        total_cits = 0
        for p, pa in pubs:
            s_res = await session.execute(select(PublicationSource).where(PublicationSource.publication_id == p.id))
            sources = s_res.scalars().all()
            src_list = [f"{s.source_system} (id={s.source_id})" for s in sources]
            venue = p.journal_name or p.conference_name
            print(f"ID: {p.id}")
            print(f"Title: {p.title}")
            print(f"Year: {p.year} | DOI: {p.doi} | Venue: {venue}")
            print(f"Authors: {p.authors_raw}")
            print(f"Publication Status: {p.verification_status} (conf={p.attribution_confidence})")
            print(f"Author Link Method: {pa.attribution_method} (conf={pa.attribution_confidence})")
            print(f"Sources: {', '.join(src_list)}")
            print(f"Citations: total={p.citation_count}, source={p.citation_source}")
            print("-" * 60)
            if p.citation_count:
                total_cits += p.citation_count

        print(f"Sum of citation_count across Siva's publications: {total_cits}")

        # 4. Metrics table
        from app.models.metrics import FacultyMetricSnapshot, CitationSnapshot
        m_res = await session.execute(select(FacultyMetricSnapshot).where(FacultyMetricSnapshot.faculty_id == fp.id).order_by(FacultyMetricSnapshot.created_at.desc()))
        metrics = m_res.scalars().all()
        print(f"\n=== FACULTY METRICS SNAPSHOTS ({len(metrics)}) ===")
        for m in metrics:
            print(f"Created: {m.created_at} | Date: {m.snapshot_date} | Total Pubs: {m.total_publications} | Verified Pubs: {m.verified_publications} | Citations: {m.total_citations} | h-index: {m.h_index} | i10-index: {m.i10_index}")

        # Citation snapshots for Siva's publications
        pub_ids = [p.id for p, pa in pubs]
        cs_res = await session.execute(select(CitationSnapshot).where(CitationSnapshot.publication_id.in_(pub_ids)))
        cs_list = cs_res.scalars().all()
        print(f"\n=== CITATION SNAPSHOTS FOR SIVA PUBS ({len(cs_list)}) ===")
        for cs in cs_list:
            print(f"Pub ID: {cs.publication_id} | Count: {cs.citation_count} | Source: {cs.source} | Date: {cs.snapshot_date}")

        # 5. Global counts
        total_fps = (await session.execute(select(func.count(FacultyProfile.id)))).scalar_one()
        total_pubs = (await session.execute(select(func.count(Publication.id)))).scalar_one()
        total_sources = (await session.execute(select(func.count(PublicationSource.id)))).scalar_one()
        total_authors = (await session.execute(select(func.count(PublicationAuthor.id)))).scalar_one()
        print(f"\n=== GLOBAL DATABASE TOTALS ===")
        print(f"Faculty Profiles: {total_fps}")
        print(f"Canonical Publications: {total_pubs}")
        print(f"Publication Sources: {total_sources}")
        print(f"Publication Authors: {total_authors}")

if __name__ == "__main__":
    asyncio.run(audit())
