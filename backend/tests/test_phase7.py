import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.publication import Publication, PublicationSource
from app.models.review import ReviewTask
from app.agents.enrichment_agent import ResearchMetadataEnrichmentAgent

@pytest.fixture
def sample_publications():
    pub1 = Publication(
        id=uuid.uuid4(),
        title="Valid Enrichment",
    )
    src1 = PublicationSource(
        publication_id=pub1.id,
        source_system="openalex",
        raw_metadata={
            "primary_location": {
                "source": {
                    "host_organization_name": "Elsevier BV",
                    "issn": ["1234-5678"]
                }
            },
            "open_access": {"is_oa": True},
            "concepts": [{"display_name": "Machine Learning"}]
        }
    )
    pub1.sources = [src1]

    pub2 = Publication(
        id=uuid.uuid4(),
        title="Conflicting Metadata",
    )
    src2_oa = PublicationSource(
        publication_id=pub2.id,
        source_system="openalex",
        raw_metadata={
            "primary_location": {
                "source": {
                    "host_organization_name": "Elsevier BV"
                }
            }
        }
    )
    src2_cr = PublicationSource(
        publication_id=pub2.id,
        source_system="crossref",
        raw_metadata={
            "publisher": "Totally Different Publisher"
        }
    )
    pub2.sources = [src2_oa, src2_cr]

    pub3 = Publication(
        id=uuid.uuid4(),
        title="Already Enriched",
        publisher="IEEE" # Should not be overwritten
    )
    src3 = PublicationSource(
        publication_id=pub3.id,
        source_system="crossref",
        raw_metadata={
            "publisher": "Institute of Electrical and Electronics Engineers"
        }
    )
    pub3.sources = [src3]

    return [pub1, pub2, pub3]


@pytest.mark.asyncio
async def test_enrichment_agent(sample_publications):
    mock_session = AsyncMock(spec=AsyncSession)
    
    def execute_side_effect(stmt):
        if "ReviewTask" in str(stmt):
            mock_res = MagicMock()
            mock_res.scalars.return_value.all.return_value = []
            return mock_res
        else:
            mock_res = MagicMock()
            mock_res.scalars.return_value.unique.return_value.all.return_value = sample_publications
            return mock_res
            
    mock_session.execute.side_effect = execute_side_effect
    
    agent = ResearchMetadataEnrichmentAgent(mock_session)
    stats = await agent.run()
    
    assert stats["processed"] == 3
    assert stats["enriched"] == 1
    assert stats["conflicts"] == 1
    
    # Pub1 was enriched
    assert sample_publications[0].publisher == "Elsevier BV"
    assert sample_publications[0].issn == "1234-5678"
    assert sample_publications[0].open_access is True
    assert "Machine Learning" in sample_publications[0].keywords
    
    # Pub2 had a conflict on publisher, so publisher wasn't set, review task created
    assert sample_publications[1].publisher is None
    
    # Pub3 was already enriched with "IEEE", should not be changed to "Institute..."
    assert sample_publications[2].publisher == "IEEE"
    
    # Provenance and ReviewTask counts
    # Pub1 fields enriched: publisher, issn, open_access, keywords = 4 provenance records
    # Pub2 fields enriched: 0 (1 conflict) -> 1 ReviewTask
    # Total add calls = 5
    assert mock_session.add.call_count == 5
