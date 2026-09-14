import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.faculty import FacultyProfile
from app.models.publication import Publication, PublicationAuthor
from app.models.review import ReviewTask
from app.agents.research_assistant_agent import ResearchAssistantAgent

@pytest.mark.asyncio
async def test_research_assistant_faculty_publications():
    """Test faculty querying their own publications with isolation."""
    fac_id = uuid.uuid4()
    mock_fac = FacultyProfile(
        id=fac_id,
        raw_name="Dr. M. Umadevi",
        normalized_name="m umadevi",
        department="CSE",
        designation="Professor",
        institutional_email="druma_cse@vignan.ac.in"
    )
    mock_user = User(
        id=uuid.uuid4(),
        email="druma_cse@vignan.ac.in",
        role="faculty",
        faculty_id=fac_id
    )

    pub1 = Publication(
        id=uuid.uuid4(),
        title="3D U-Net Segmentation for Brain Tumor",
        year=2023,
        journal_name="IEEE Trans",
        citation_count=42,
        verification_status="VERIFIED",
        doi="10.1109/test.123"
    )
    pub1.sources = []
    pub1.authors = []

    mock_session = AsyncMock(spec=AsyncSession)

    def execute_side_effect(stmt):
        str_stmt = str(stmt).lower()
        mock_res = MagicMock()
        if "faculty_profiles" in str_stmt:
            mock_res.scalars.return_value.first.return_value = mock_fac
            mock_res.scalars.return_value.all.return_value = [mock_fac]
        elif "publication_authors" in str_stmt:
            mock_res.scalars.return_value.all.return_value = [pub1.id]
        elif "publications" in str_stmt:
            mock_res.scalars.return_value.unique.return_value.all.return_value = [pub1]
            mock_res.scalars.return_value.all.return_value = [pub1]
        else:
            mock_res.scalars.return_value.all.return_value = []
        return mock_res

    mock_session.execute.side_effect = execute_side_effect

    agent = ResearchAssistantAgent(mock_session, mock_user)
    res = await agent.answer_query("What are my top cited publications?")

    assert "3D U-Net Segmentation for Brain Tumor" in res["answer"]
    assert "42" in res["answer"]
    assert len(res["citations"]) == 1
    assert res["citations"][0]["doi"] == "10.1109/test.123"
    assert "VFSTR Institutional Database" in res["provenance"]

@pytest.mark.asyncio
async def test_research_assistant_metrics_and_h_index():
    """Test metrics and h-index computation grounded in real data."""
    fac_id = uuid.uuid4()
    mock_fac = FacultyProfile(
        id=fac_id,
        raw_name="Dr. Bhimavarapu Krishna Reddy",
        normalized_name="bhimavarapu krishna reddy",
        department="CSE"
    )
    mock_user = User(
        id=uuid.uuid4(),
        email="bkr_cse@vignan.ac.in",
        role="faculty",
        faculty_id=fac_id
    )

    # 3 publications with citations: 25, 12, 2 -> h-index = 2, i10-index = 2
    pub1 = Publication(id=uuid.uuid4(), title="Paper A", year=2022, citation_count=25, verification_status="VERIFIED")
    pub2 = Publication(id=uuid.uuid4(), title="Paper B", year=2023, citation_count=12, verification_status="VERIFIED")
    pub3 = Publication(id=uuid.uuid4(), title="Paper C", year=2024, citation_count=2, verification_status="VERIFIED")

    for p in (pub1, pub2, pub3):
        p.sources = []
        p.authors = []

    mock_session = AsyncMock(spec=AsyncSession)

    def execute_side_effect(stmt):
        str_stmt = str(stmt).lower()
        mock_res = MagicMock()
        if "faculty_profiles" in str_stmt:
            mock_res.scalars.return_value.first.return_value = mock_fac
        elif "publication_authors" in str_stmt:
            mock_res.scalars.return_value.all.return_value = [pub1.id, pub2.id, pub3.id]
        elif "publications" in str_stmt:
            mock_res.scalars.return_value.unique.return_value.all.return_value = [pub1, pub2, pub3]
        return mock_res

    mock_session.execute.side_effect = execute_side_effect

    agent = ResearchAssistantAgent(mock_session, mock_user)
    res = await agent.answer_query("What is my current h-index and citation impact?")

    assert "h-index" in res["answer"]
    assert "39" in res["answer"] # 25+12+2 = 39 total citations
    assert len(res["citations"]) == 3
    assert "VFSTR Metrics Agent" in res["provenance"]
