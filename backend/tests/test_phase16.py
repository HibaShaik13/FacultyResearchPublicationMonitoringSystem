"""
Phase 16 — Research Intelligence Graph & Collaboration Networks Test Suite.
Verifies collaboration network generation, knowledge graph multi-entity linkages,
tailored grant opportunities, and research area domain analytics.
"""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.faculty import FacultyProfile
from app.models.publication import Publication, PublicationAuthor
from app.services.research_intelligence_service import ResearchIntelligenceService


@pytest.mark.asyncio
async def test_collaborations_network_generation():
    """Test generating collaboration network from faculty profiles and affinities."""
    fac1_id = uuid.uuid4()
    fac2_id = uuid.uuid4()

    fac1 = FacultyProfile(
        id=fac1_id,
        raw_name="Dr. M. Umadevi",
        normalized_name="m umadevi",
        department="CSE",
        designation="Associate Professor",
        research_interests=["Image Processing", "Machine Learning", "Forensics"]
    )
    fac2 = FacultyProfile(
        id=fac2_id,
        raw_name="Dr. V. Phani Kumar",
        normalized_name="venkatrama phani kumar s",
        department="CSE",
        designation="Professor",
        research_interests=["Machine Learning", "Text Mining"]
    )

    mock_session = AsyncMock(spec=AsyncSession)

    def execute_side_effect(stmt):
        str_stmt = str(stmt).lower()
        mock_res = MagicMock()
        if "from faculty_profiles" in str_stmt:
            mock_res.scalars.return_value.all.return_value = [fac1, fac2]
        elif "publication_authors" in str_stmt:
            mock_res.all.return_value = [(fac1_id, 17, 0), (fac2_id, 8, 0)]
        else:
            mock_res.scalars.return_value.all.return_value = []
            mock_res.all.return_value = []
        return mock_res

    mock_session.execute.side_effect = execute_side_effect

    service = ResearchIntelligenceService(mock_session)
    network = await service.get_collaborations_network()

    assert network["total_nodes"] == 2
    assert network["total_edges"] >= 1
    assert network["departments_count"] == 1
    assert any(e["source"] == str(fac1_id) and e["target"] == str(fac2_id) for e in network["edges"])


@pytest.mark.asyncio
async def test_knowledge_graph_multi_entity():
    """Test multi-tier knowledge graph with departments, faculty, pubs, and venues."""
    fac_id = uuid.uuid4()
    pub_id = uuid.uuid4()

    fac = FacultyProfile(
        id=fac_id,
        raw_name="Dr. Prashant Upadhyay",
        normalized_name="prashant upadhyay",
        department="CSE",
        designation="Associate Professor",
        research_interests=["Cloud Computing", "AI"]
    )
    pub = Publication(
        id=pub_id,
        title="Scalable Multi-Agent Cloud Architecture",
        year=2024,
        journal_name="IEEE Transactions on Services Computing",
        citation_count=12,
        verification_status="verified"
    )

    mock_session = AsyncMock(spec=AsyncSession)

    def execute_side_effect(stmt):
        str_stmt = str(stmt).lower()
        mock_res = MagicMock()
        if "from faculty_profiles" in str_stmt:
            mock_res.scalars.return_value.all.return_value = [fac]
        elif "from publications" in str_stmt:
            mock_res.all.return_value = [(pub, fac_id)]
        else:
            mock_res.scalars.return_value.all.return_value = []
            mock_res.all.return_value = []
        return mock_res

    mock_session.execute.side_effect = execute_side_effect

    service = ResearchIntelligenceService(mock_session)
    kg = await service.get_knowledge_graph()

    assert kg["total_nodes"] >= 4  # Department, Faculty, Publication, Venue
    assert kg["total_edges"] >= 3
    node_types = set(n["type"] for n in kg["nodes"])
    assert "Department" in node_types
    assert "Faculty" in node_types
    assert "Publication" in node_types


@pytest.mark.asyncio
async def test_research_opportunities_matching():
    """Test matching research grants to faculty domain expertise."""
    fac_id = uuid.uuid4()
    fac = FacultyProfile(
        id=fac_id,
        raw_name="Dr. M. Umadevi",
        normalized_name="m umadevi",
        department="CSE",
        research_interests=["Image Processing", "Document Forensics", "Computer Vision"]
    )

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.get.return_value = fac

    service = ResearchIntelligenceService(mock_session)
    opps = await service.get_research_opportunities(faculty_id=fac_id)

    assert len(opps) > 0
    # The top opportunity should have high relevance score (>= 80)
    assert opps[0]["relevance_score"] >= 80
    assert "title" in opps[0]
    assert "grant_amount" in opps[0]
    assert "agency" in opps[0]
