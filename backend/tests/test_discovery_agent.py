import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.faculty import FacultyProfile
from app.models.publication import Publication, PublicationSource
from app.models.provenance import ProvenanceRecord
from app.agents.discovery_agent import PublicationDiscoveryAgent

@pytest.fixture
def test_profile():
    return FacultyProfile(
        id=uuid.uuid4(),
        raw_name="Dr Test Faculty",
        normalized_name="test faculty",
        status="active"
    )

@pytest.fixture
def mock_openalex():
    with patch("app.agents.discovery_agent.OpenAlexClient.search_works_by_name", new_callable=AsyncMock) as mock:
        yield mock

@pytest.fixture
def mock_crossref():
    with patch("app.agents.discovery_agent.CrossrefClient.search_works_by_author", new_callable=AsyncMock) as mock:
        yield mock

@pytest.mark.asyncio
async def test_discovery_agent_new_publications(mock_openalex, mock_crossref, test_profile):
    """Test discovering new publications from both sources."""
    mock_openalex.return_value = [
        {
            "id": "openalex:W123",
            "title": "OpenAlex Paper",
            "doi": "https://doi.org/10.123/oa",
            "publication_year": 2025,
            "authorships": [{"institutions": [{"display_name": "Vignan University"}]}]
        }
    ]
    
    mock_crossref.return_value = [
        {
            "DOI": "10.456/cr",
            "title": ["Crossref Paper"],
            "issued": {"date-parts": [[2025, 5, 1]]}
        }
    ]
    
    mock_session = AsyncMock(spec=AsyncSession)
    
    # Mock returning variants for initial query
    mock_variants_result = MagicMock()
    mock_variants_result.all.return_value = [("Vignan University",)]

    # Mock returning profile for select profiles
    mock_profile_result = MagicMock()
    mock_profile_result.scalars.return_value.all.return_value = [test_profile]
    
    # Mock returning nothing for existing source/doi/title checks (2 pubs * 3 checks = 6 checks)
    mock_empty_result = MagicMock()
    mock_empty_result.scalars.return_value.first.return_value = None
    
    mock_session.execute.side_effect = [
        mock_variants_result,
        mock_profile_result,
        mock_empty_result,
        mock_empty_result,
        mock_empty_result,
        mock_empty_result,
        mock_empty_result,
        mock_empty_result
    ]
    
    agent = PublicationDiscoveryAgent(mock_session)
    stats = await agent.run()
    
    assert stats["processed"] == 1
    assert stats["publications_discovered"] == 2
    assert stats["dois_found"] == 2
    assert stats["duplicates_prevented"] == 0
    
    # For each pub: Publication + Source + Provenance = 3 objects per pub = 6 total adds
    assert mock_session.add.call_count == 6

@pytest.mark.asyncio
async def test_discovery_agent_idempotency(mock_openalex, mock_crossref, test_profile):
    """Test that existing sources skip creation."""
    mock_openalex.return_value = [
        {
            "id": "openalex:W123",
            "title": "OpenAlex Paper",
            "authorships": [{"institutions": [{"display_name": "Vignan University"}]}]
        }
    ]
    
    mock_crossref.return_value = []
    
    mock_session = AsyncMock(spec=AsyncSession)
    
    mock_variants_result = MagicMock()
    mock_variants_result.all.return_value = [("Vignan University",)]

    mock_profile_result = MagicMock()
    mock_profile_result.scalars.return_value.all.return_value = [test_profile]
    
    mock_existing_result = MagicMock()
    mock_existing_result.scalars.return_value.first.return_value = PublicationSource()
    
    mock_session.execute.side_effect = [mock_variants_result, mock_profile_result, mock_existing_result]
    
    agent = PublicationDiscoveryAgent(mock_session)
    stats = await agent.run()
    
    assert stats["processed"] == 1
    assert stats["publications_discovered"] == 0
    assert stats["duplicates_prevented"] == 1
    
    # No objects added
    assert mock_session.add.call_count == 0
