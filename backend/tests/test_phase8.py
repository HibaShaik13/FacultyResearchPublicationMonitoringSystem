import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.publication import Publication, PublicationSource
from app.models.review import ReviewTask
from app.agents.integrity_agent import ResearchIntegrityAgent

@pytest.fixture
def sample_publications():
    # 1. Clean pub
    pub1 = Publication(id=uuid.uuid4(), title="Clean", doi="10.123/456", risk_level="none")
    src1 = PublicationSource(
        publication_id=pub1.id,
        source_system="openalex",
        raw_metadata={"title": "Clean", "publication_year": 2023}
    )
    pub1.sources = [src1]

    # 2. Invalid DOI
    pub2 = Publication(id=uuid.uuid4(), title="Invalid DOI", doi="99.99/xyz", risk_level="none")
    pub2.sources = []

    # 3. Year conflict (>1 year diff)
    pub3 = Publication(id=uuid.uuid4(), title="Year conflict", doi="10.123/789", risk_level="none")
    src3_oa = PublicationSource(
        publication_id=pub3.id,
        source_system="openalex",
        raw_metadata={"title": "Year conflict", "publication_year": 2020}
    )
    src3_cr = PublicationSource(
        publication_id=pub3.id,
        source_system="crossref",
        raw_metadata={"title": ["Year conflict"], "published": {"date-parts": [[2022]]}}
    )
    pub3.sources = [src3_oa, src3_cr]

    # 4. Title conflict (severe) -> HIGH
    pub4 = Publication(id=uuid.uuid4(), title="Title A", doi="10.111/222", risk_level="none")
    src4_oa = PublicationSource(
        publication_id=pub4.id,
        source_system="openalex",
        raw_metadata={"title": "Machine Learning in Healthcare", "publication_year": 2023}
    )
    src4_cr = PublicationSource(
        publication_id=pub4.id,
        source_system="crossref",
        raw_metadata={"title": ["An entirely different paper about History"], "published": {"date-parts": [[2023]]}}
    )
    pub4.sources = [src4_oa, src4_cr]

    # 5. Missing DOI
    pub5 = Publication(id=uuid.uuid4(), title="No DOI", doi=None, risk_level="none")
    pub5.sources = []

    return [pub1, pub2, pub3, pub4, pub5]


@pytest.mark.asyncio
async def test_integrity_agent(sample_publications):
    mock_session = AsyncMock(spec=AsyncSession)
    
    def execute_side_effect(stmt):
        if "review_tasks" in str(stmt):
            mock_res = MagicMock()
            mock_res.scalars.return_value.first.return_value = None
            return mock_res
        else:
            mock_res = MagicMock()
            mock_res.scalars.return_value.unique.return_value.all.return_value = sample_publications
            return mock_res
            
    mock_session.execute.side_effect = execute_side_effect
    
    agent = ResearchIntegrityAgent(mock_session)
    stats = await agent.run()
    
    assert stats["processed"] == 5
    
    # 1. Clean -> none
    assert sample_publications[0].risk_level == "none"
    
    # 2. Invalid DOI -> medium
    assert sample_publications[1].risk_level == "medium"
    assert "invalid_doi" in sample_publications[1].risk_reasons
    
    # 3. Year conflict -> medium
    assert sample_publications[2].risk_level == "medium"
    assert "year_conflict" in sample_publications[2].risk_reasons
    
    # 4. Title conflict -> high
    assert sample_publications[3].risk_level == "high"
    assert "title_conflict" in sample_publications[3].risk_reasons
    
    # 5. Missing DOI -> low
    assert sample_publications[4].risk_level == "low"
    assert "missing_doi" in sample_publications[4].risk_reasons
    
    assert stats["low"] == 1
    assert stats["medium"] == 2
    assert stats["high"] == 1
    assert stats["review_required"] == 1
    
    # Provenance counts: 4 objects had risk > 0 (1 low, 2 medium, 1 high) -> 4 provenance records
    # 1 ReviewTask for high risk
    # Total add calls = 5
    assert mock_session.add.call_count == 5
