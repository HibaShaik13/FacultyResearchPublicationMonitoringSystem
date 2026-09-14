import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.publication import Publication, PublicationSource
from app.models.review import ReviewTask
from app.agents.metadata_normalization_agent import MetadataNormalizationAgent
from app.agents.deduplication_agent import DeduplicationAgent

@pytest.fixture
def sample_publications():
    pub1_id = uuid.uuid4()
    pub2_id = uuid.uuid4()
    pub3_id = uuid.uuid4()
    
    # Exact DOI duplicate
    pub1 = Publication(
        id=pub1_id,
        title="Testing the system",
        normalized_title="testing the system",
        doi="https://doi.org/10.123/456",
        year=2023
    )
    src1 = PublicationSource(
        publication_id=pub1_id,
        source_system="crossref",
        source_id="10.123/456",
        raw_metadata={"author": [{"given": "John", "family": "Doe"}], "type": "journal-article", "container-title": ["Test Journal"]}
    )
    pub1.sources = [src1]
    
    pub2 = Publication(
        id=pub2_id,
        title="Testing the System",
        normalized_title="testing the system",
        doi="http://doi.org/10.123/456 ",
        year=2023
    )
    src2 = PublicationSource(
        publication_id=pub2_id,
        source_system="openalex",
        source_id="W123",
        raw_metadata={"authorships": [{"author": {"display_name": "John Doe"}}], "type": "article", "primary_location": {"source": {"display_name": "Test Journal"}}}
    )
    pub2.sources = [src2]
    
    # Fuzzy duplicate (No DOI)
    pub3 = Publication(
        id=pub3_id,
        title="Testing the System: A review",
        normalized_title="testing the system a review", # high match with 'testing the system: a review'
        doi=None,
        year=2023
    )
    src3 = PublicationSource(
        publication_id=pub3_id,
        source_system="openalex",
        source_id="W456",
        raw_metadata={}
    )
    pub3.sources = [src3]
    
    pub4 = Publication(
        id=uuid.uuid4(),
        title="Testing the system: A review",
        normalized_title="testing the system a review",
        doi=None,
        year=2023
    )
    src4 = PublicationSource(
        publication_id=pub4.id,
        source_system="crossref",
        source_id="10.123/789",
        raw_metadata={}
    )
    pub4.sources = [src4]
    
    return [pub1, pub2, pub3, pub4]


@pytest.mark.asyncio
async def test_metadata_normalization(sample_publications):
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.unique.return_value.all.return_value = sample_publications
    mock_session.execute.return_value = mock_result
    
    agent = MetadataNormalizationAgent(mock_session)
    stats = await agent.run()
    
    assert stats["processed"] == 4
    assert stats["normalized"] == 4
    assert stats["errors"] == 0
    
    # Check DOI normalization
    assert sample_publications[0].doi == "10.123/456"
    assert sample_publications[1].doi == "10.123/456"
    
    # Check parsed authors
    assert len(sample_publications[0].authors_parsed) == 1
    assert sample_publications[0].authors_parsed[0]["name"] == "John Doe"
    
    # Check pub type mapping
    assert sample_publications[0].publication_type == "journal-article"
    assert sample_publications[1].publication_type == "journal-article"


@pytest.mark.asyncio
async def test_deduplication(sample_publications):
    # Setup - pre-normalize DOIs and titles so dedup works
    sample_publications[0].doi = "10.123/456"
    sample_publications[1].doi = "10.123/456"
    
    mock_session = AsyncMock(spec=AsyncSession)
    
    # Needs to handle the initial select and the ReviewTask idempotency select
    def execute_side_effect(stmt):
        if "ReviewTask" in str(stmt):
            mock_empty = MagicMock()
            mock_empty.scalars.return_value.first.return_value = None
            return mock_empty
        else:
            mock_res = MagicMock()
            mock_res.scalars.return_value.unique.return_value.all.return_value = sample_publications
            return mock_res
            
    mock_session.execute.side_effect = execute_side_effect
    # Make 'in' check pass
    deleted_items = set()
    def mock_delete(item):
        deleted_items.add(item)
    mock_session.delete.side_effect = mock_delete
    mock_session.__contains__.side_effect = lambda item: item not in deleted_items
    
    agent = DeduplicationAgent(mock_session)
    stats = await agent.run()
    
    # 2 DOIs match exact (1 merge), 2 fuzzy match exact (1 merge) -> Total 2 merged
    assert stats["merged"] == 2
    
    # Check that session.delete was called twice (for the two duplicates)
    assert mock_session.delete.call_count == 2
