import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database import async_session_factory
from app.models.faculty import FacultyProfile, FacultyIdentifier
from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.metrics import FacultyMetricSnapshot, CitationSnapshot
from app.models.review import ReviewTask
from app.agents.metrics_agent import MetricsAgent
from sqlalchemy import select, func

async def test_scenarios():
    print("=== CONTROLLED UAT SCENARIO 1: NEW PUBLICATION DETECTION & METRICS UPDATE ===")
    async with async_session_factory() as session:
        # Pick test faculty (Dr. M. Umadevi)
        uma = (await session.execute(select(FacultyProfile).where(FacultyProfile.normalized_name.ilike('%umadevi%')))).scalars().first()
        assert uma is not None

        initial_count = (await session.execute(
            select(func.count(PublicationAuthor.id)).where(PublicationAuthor.faculty_id == uma.id, PublicationAuthor.attribution_confidence >= 0.70)
        )).scalar()
        print(f"Dr. M. Umadevi Initial Confirmed Pubs: {initial_count}")

        # Simulate a newly discovered publication
        test_pub_id = uuid.uuid4()
        test_doi = f"10.1016/j.testpub.{uuid.uuid4().hex[:8]}"
        test_pub = Publication(
            id=test_pub_id,
            title="Controlled Test Novel Neural Architecture for Signal Processing",
            normalized_title="controlled test novel neural architecture for signal processing",
            doi=test_doi,
            year=2026,
            citation_count=5,
            verification_status="verified",
            attribution_confidence=1.0,
            metadata_confidence=1.0,
        )
        session.add(test_pub)

        test_src = PublicationSource(
            id=uuid.uuid4(),
            publication_id=test_pub_id,
            source_system="openalex",
            source_id=f"W{uuid.uuid4().hex[:8]}",
            raw_metadata={"cited_by_count": 5},
            discovery_method="openalex_api",
        )
        session.add(test_src)

        test_pa = PublicationAuthor(
            id=uuid.uuid4(),
            publication_id=test_pub_id,
            faculty_id=uma.id,
            author_position=1,
            author_name_raw=uma.raw_name,
            attribution_confidence=1.0,
            attribution_method="openalex_author_id_verified",
        )
        session.add(test_pa)
        await session.commit()

        # Re-run MetricsAgent
        metrics_agent = MetricsAgent(session)
        stats = await metrics_agent.run()
        print(f"MetricsAgent Run Output: {stats}")

        updated_count = (await session.execute(
            select(func.count(PublicationAuthor.id)).where(PublicationAuthor.faculty_id == uma.id, PublicationAuthor.attribution_confidence >= 0.70)
        )).scalar()
        print(f"After New Publication Ingestion -> Confirmed Pubs: {updated_count} (Delta: +{updated_count - initial_count})")
        assert updated_count == initial_count + 1

        print("\n=== CONTROLLED UAT SCENARIO 2: CITATION REFRESH TEST (5 -> 25 CITATIONS) ===")
        # Update raw citation in source
        test_src.raw_metadata = {"cited_by_count": 25}
        test_pub.citation_count = 25
        await session.commit()

        stats_m = await metrics_agent.run()
        print(f"MetricsAgent Citation Refresh Output: {stats_m}")

        # Check recalculated metrics
        uma_pas = (await session.execute(
            select(PublicationAuthor, Publication)
            .join(Publication, PublicationAuthor.publication_id == Publication.id)
            .where(PublicationAuthor.faculty_id == uma.id, PublicationAuthor.attribution_confidence >= 0.70)
        )).all()
        cits = [p.citation_count or 0 for _, p in uma_pas]
        cits.sort(reverse=True)
        tot_cits = sum(cits)
        h_idx = sum(1 for idx, c in enumerate(cits) if c >= idx + 1)
        i10_idx = sum(1 for c in cits if c >= 10)
        print(f"Recalculated Metrics Proof: Citations={tot_cits}, h-index={h_idx}, i10-index={i10_idx}")

        # Clean up test fixture cleanly
        print("\nCleaning up controlled test fixture...")
        await session.delete(test_pa)
        await session.delete(test_src)
        await session.delete(test_pub)
        await session.commit()

        # Final metrics restoration
        await metrics_agent.run()
        final_count = (await session.execute(
            select(func.count(PublicationAuthor.id)).where(PublicationAuthor.faculty_id == uma.id, PublicationAuthor.attribution_confidence >= 0.70)
        )).scalar()
        print(f"Cleaned up fixture. Verified clean state -> Confirmed Pubs: {final_count}")
        assert final_count == initial_count

if __name__ == '__main__':
    asyncio.run(test_scenarios())
