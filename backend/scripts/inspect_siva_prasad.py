import asyncio
import json
import sys
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
import httpx

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from app.database import async_session_factory
from app.models.faculty import FacultyProfile, FacultyIdentifier, FacultyNameVariant
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.metrics import FacultyMetricSnapshot, CitationSnapshot
from app.main import app

async def main():
    async with async_session_factory() as session:
        # Find Dr. P. Siva Prasad
        stmt = (
            select(FacultyProfile)
            .options(
                selectinload(FacultyProfile.identifiers),
                selectinload(FacultyProfile.name_variants),
                selectinload(FacultyProfile.metric_snapshots),
                selectinload(FacultyProfile.publication_links).selectinload(PublicationAuthor.publication),
            )
            .where(
                (FacultyProfile.institutional_email == "drpsp_cse@vignan.ac.in") |
                (FacultyProfile.normalized_name == "p. siva prasad")
            )
        )
        res = await session.execute(stmt)
        fac = res.scalars().first()

        if not fac:
            print("ERROR: Dr. P. Siva Prasad not found in database.")
            return

        print("===================================================================")
        print("DATABASE RECORD: DR. P. SIVA PRASAD")
        print("===================================================================")
        print(f"Faculty ID: {fac.id}")
        print(f"Faculty Name: {fac.raw_name}")
        print(f"Normalized Name: {fac.normalized_name}")
        print(f"Department: {fac.department}")
        print(f"Designation: {fac.designation}")
        print(f"Institutional Email: {fac.institutional_email}")
        print(f"Phone: {fac.phone}")
        print(f"Research Interests: {fac.research_interests}")
        print(f"Education: {fac.education}")
        print(f"Teaching: {fac.teaching_engagements}")
        print(f"Administrative: {fac.administrative_positions}")
        print(f"Status: {fac.status}")

        print("\n--- SCHOLARLY IDENTIFIERS ---")
        if fac.identifiers:
            for ident in fac.identifiers:
                print(f"  * [{ident.identifier_type}] {ident.identifier_value} (confidence={ident.confidence}, verified={ident.verified}, source={ident.source})")
        else:
            print("  (No external scholarly identifiers resolved with high confidence)")

        print("\n--- NAME VARIANTS ---")
        for nv in fac.name_variants:
            print(f"  * {nv.name_variant} (source={nv.variant_source})")

        print(f"\n--- ATTRIBUTED PUBLICATIONS ({len(fac.publication_links)}) ---")
        unique_pubs = {}
        for link in fac.publication_links:
            p = link.publication
            if p and p.id not in unique_pubs:
                unique_pubs[p.id] = (link, p)

        citation_sources = set()
        for link, p in list(unique_pubs.values())[:10]:
            if p.citation_source:
                citation_sources.add(p.citation_source)
            print(f"  * Title: {p.title}")
            print(f"    DOI: {p.doi}")
            print(f"    Citation Count: {p.citation_count}")
            print(f"    Citation Source: {p.citation_source}")
            print(f"    Attribution Confidence: {link.attribution_confidence}")
            print(f"    Author Position: {link.author_position}")
            print(f"    Verification Status: {p.verification_status}")
            print()

        print(f"Total Unique Attributed Publications: {len(unique_pubs)}")
        print(f"Total PublicationAuthor links: {len(fac.publication_links)}")
        print(f"Citation Sources Encountered: {list(citation_sources)}")

        print("\n--- FACULTY METRIC SNAPSHOTS ---")
        for s in fac.metric_snapshots:
            print(f"  * Snapshot Date: {s.snapshot_date}")
            print(f"    Total Publications: {s.total_publications}")
            print(f"    Total Citations: {s.total_citations}")
            print(f"    h-index: {s.h_index}")
            print(f"    i10-index: {s.i10_index}")

        # Count total faculty in DB
        count_stmt = select(func.count(FacultyProfile.id))
        total_fac = (await session.execute(count_stmt)).scalar()
        print(f"\nTotal Faculty Records in Database: {total_fac}")

    print("\n===================================================================")
    print("REST API VERIFICATION")
    print("===================================================================")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # GET /api/v1/faculty/{id}
        f_resp = await client.get(f"/api/v1/faculty/{fac.id}")
        print(f"GET /api/v1/faculty/{fac.id} -> Status: {f_resp.status_code}")
        f_data = f_resp.json()
        print(f"  Name: {f_data.get('raw_name')}")
        print(f"  Department: {f_data.get('department')}")
        print(f"  Email: {f_data.get('institutional_email')}")
        print(f"  Total Publications: {f_data.get('total_publications')}")
        print(f"  Total Citations: {f_data.get('total_citations')}")
        print(f"  h-index: {f_data.get('h_index')}")
        print(f"  i10-index: {f_data.get('i10_index')}")

        # GET /api/v1/analytics/dashboard?faculty_id={id}
        d_resp = await client.get(f"/api/v1/analytics/dashboard?faculty_id={fac.id}")
        print(f"\nGET /api/v1/analytics/dashboard?faculty_id={fac.id} -> Status: {d_resp.status_code}")
        d_data = d_resp.json()
        print(f"  Overview Cards:")
        print(f"    Total Publications: {d_data.get('overview', {}).get('total_publications')}")
        print(f"    Total Citations: {d_data.get('overview', {}).get('total_citations')}")
        print(f"    h-index: {d_data.get('overview', {}).get('h_index')}")
        print(f"    i10-index: {d_data.get('overview', {}).get('i10_index')}")

        # GET /api/v1/publications/?faculty_id={id}
        p_resp = await client.get(f"/api/v1/publications/?faculty_id={fac.id}")
        print(f"\nGET /api/v1/publications/?faculty_id={fac.id} -> Status: {p_resp.status_code}, Total: {p_resp.json().get('total')}")

        # GET /api/v1/publications/stats
        s_resp = await client.get("/api/v1/publications/stats")
        print(f"\nGET /api/v1/publications/stats -> Status: {s_resp.status_code}")
        print("  Stats:", json.dumps(s_resp.json(), indent=2))

if __name__ == "__main__":
    asyncio.run(main())
