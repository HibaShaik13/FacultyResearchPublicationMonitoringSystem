import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.faculty import FacultyProfile
from app.models.review import ReviewTask
from app.models.provenance import ProvenanceRecord
from app.agents.identity_agent import FacultyIdentityAgent

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
    with patch("app.agents.identity_agent.OpenAlexClient.search_authors", new_callable=AsyncMock) as mock:
        yield mock

@pytest.mark.asyncio
async def test_agent_exact_name_and_affiliation(mock_openalex, test_profile):
    """Test that a perfect name match + valid affiliation results in auto-verify (>0.85)."""
    mock_openalex.return_value = [
        {
            "id": "https://openalex.org/A123",
            "display_name": "Test Faculty",
            "last_known_institution": {
                "display_name": "Vignan's Foundation for Science, Technology & Research"
            }
        }
    ]
    
    mock_session = AsyncMock(spec=AsyncSession)
    
    # Mock the DB execute to return our test profile
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [test_profile]
    mock_session.execute.return_value = mock_result
    
    agent = FacultyIdentityAgent(mock_session)
    stats = await agent.run()
    
    assert stats["processed"] == 1
    assert stats["matched"] == 1
    assert stats["ambiguous"] == 0
    assert stats["unmatched"] == 0
    
    # Assert we added identifier and provenance, but no review task
    assert mock_session.add.call_count == 2
    
@pytest.mark.asyncio
async def test_agent_name_only_ambiguous(mock_openalex, test_profile):
    """Test that name match without affiliation results in ambiguous review (0.60-0.84)."""
    mock_openalex.return_value = [
        {
            "id": "https://openalex.org/A456",
            "display_name": "Test Faculty",
            "last_known_institution": None
        }
    ]
    
    mock_session = AsyncMock(spec=AsyncSession)
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [test_profile]
    mock_session.execute.return_value = mock_result
    
    agent = FacultyIdentityAgent(mock_session)
    stats = await agent.run()
    
    assert stats["processed"] == 1
    assert stats["matched"] == 0
    assert stats["ambiguous"] == 1
    
    # Added identifier, provenance, and ReviewTask
    assert mock_session.add.call_count == 3
    added_objects = [call.args[0] for call in mock_session.add.call_args_list]
    review_tasks = [obj for obj in added_objects if isinstance(obj, ReviewTask)]
    assert len(review_tasks) == 1
    assert review_tasks[0].task_type == "IDENTIFIER_MATCH"

@pytest.mark.asyncio
async def test_agent_no_match(mock_openalex, test_profile):
    """Test that unrelated names result in unmatched."""
    mock_openalex.return_value = [
        {
            "id": "https://openalex.org/A789",
            "display_name": "John Smith",
            "last_known_institution": None
        }
    ]
    
    mock_session = AsyncMock(spec=AsyncSession)
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [test_profile]
    mock_session.execute.return_value = mock_result
    
    agent = FacultyIdentityAgent(mock_session)
    stats = await agent.run()
    
    assert stats["processed"] == 1
    assert stats["matched"] == 0
    assert stats["ambiguous"] == 0
    assert stats["unmatched"] == 1
    
    # No objects added
    assert mock_session.add.call_count == 0
