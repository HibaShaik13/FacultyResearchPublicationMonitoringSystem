import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.publication import Publication, PublicationSource, PublicationAuthor
from app.models.faculty import FacultyProfile
from app.models.metrics import CitationSnapshot, FacultyMetricSnapshot
from app.models.provenance import ProvenanceRecord
from app.agents.metrics_agent import MetricsAgent

@pytest.fixture
def sample_data():
    pub1 = Publication(id=uuid.uuid4(), title="Pub 1", citation_count=0)
    src1_oa = PublicationSource(
        publication_id=pub1.id,
        source_system="openalex",
        raw_metadata={"cited_by_count": 10}
    )
    src1_cr = PublicationSource(
        publication_id=pub1.id,
        source_system="crossref",
        raw_metadata={"is-referenced-by-count": 12}
    )
    pub1.sources = [src1_oa, src1_cr]

    pub2 = Publication(id=uuid.uuid4(), title="Pub 2", citation_count=0)
    src2 = PublicationSource(
        publication_id=pub2.id,
        source_system="openalex",
        raw_metadata={"cited_by_count": 5}
    )
    pub2.sources = [src2]
    
    pub3 = Publication(id=uuid.uuid4(), title="Pub 3", citation_count=0)
    src3 = PublicationSource(
        publication_id=pub3.id,
        source_system="crossref",
        raw_metadata={}  # Missing metrics
    )
    pub3.sources = [src3]
    
    # After pub processing, pub1 will have 12, pub2 will have 5, pub3 will have 0.
    # Total citations = 17. h-index = 2 (12, 5). i10-index = 1 (12).

    faculty = FacultyProfile(id=uuid.uuid4(), raw_name="Test Faculty")
    
    link1 = PublicationAuthor(publication_id=pub1.id, faculty_id=faculty.id, publication=pub1)
    link2 = PublicationAuthor(publication_id=pub2.id, faculty_id=faculty.id, publication=pub2)
    link3 = PublicationAuthor(publication_id=pub3.id, faculty_id=faculty.id, publication=pub3)
    
    faculty.publication_links = [link1, link2, link3]

    return [pub1, pub2, pub3], [faculty]


@pytest.mark.asyncio
async def test_metrics_agent(sample_data):
    pubs, faculties = sample_data
    mock_session = AsyncMock(spec=AsyncSession)
    
    def execute_side_effect(stmt):
        stmt_str = str(stmt).lower()
        if "citation_snapshots" in stmt_str or "faculty_metric_snapshots" in stmt_str:
            mock_res = MagicMock()
            mock_res.scalars.return_value.first.return_value = None
            return mock_res
        elif "faculty_profiles" in stmt_str:
            mock_res = MagicMock()
            mock_res.scalars.return_value.unique.return_value.all.return_value = faculties
            return mock_res
        elif "publications" in stmt_str:
            mock_res = MagicMock()
            mock_res.scalars.return_value.unique.return_value.all.return_value = pubs
            return mock_res
            
    mock_session.execute.side_effect = execute_side_effect
    
    agent = MetricsAgent(mock_session)
    stats = await agent.run()
    
    assert stats["pub_processed"] == 3
    assert stats["faculty_processed"] == 1
    
    # 2 sources for pub1, 1 for pub2, 0 for pub3 = 3 citation snapshots
    assert stats["pub_snapshots"] == 3
    
    assert pubs[0].citation_count == 12
    assert pubs[0].citation_source == "crossref"
    
    assert pubs[1].citation_count == 5
    assert pubs[1].citation_source == "openalex"
    
    assert stats["faculty_snapshots"] == 1
    assert stats["calculated_metrics"] == 2
    assert stats["missing_metrics"] == 1
    
    # Verify add calls (3 citation snapshots + 1 faculty snapshot + 1 provenance) = 5
    assert mock_session.add.call_count == 5
