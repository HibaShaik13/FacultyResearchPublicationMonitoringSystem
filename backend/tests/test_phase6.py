import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.publication import Publication
from app.models.faculty import FacultyProfile, FacultyNameVariant
from app.models.review import ReviewTask
from app.agents.attribution_agent import FacultyAttributionAgent

@pytest.fixture
def sample_data():
    profile = FacultyProfile(
        id=uuid.uuid4(),
        raw_name="Dr. John Doe",
        normalized_name="john doe",
        status="active"
    )
    profile.name_variants = [
        FacultyNameVariant(
            id=uuid.uuid4(),
            faculty_id=profile.id,
            name_variant="j. doe"
        )
    ]
    
    pub1 = Publication(
        id=uuid.uuid4(),
        title="High Confidence Match",
        authors_parsed=[{
            "name": "John Doe",
            "affiliations": ["Vignan University"],
            "position": 1
        }]
    )
    
    pub2 = Publication(
        id=uuid.uuid4(),
        title="Ambiguous Match",
        authors_parsed=[{
            "name": "Jonathan Doe",
            "affiliations": ["Unknown Inst"],
            "position": 1
        }]
    )
    
    pub3 = Publication(
        id=uuid.uuid4(),
        title="No Match",
        authors_parsed=[{
            "name": "Jane Smith",
            "affiliations": ["Other Univ"],
            "position": 1
        }]
    )
    
    pub4 = Publication(
        id=uuid.uuid4(),
        title="Variant Match",
        authors_parsed=[{
            "name": "J. Doe",
            "affiliations": ["VFSTR"],
            "position": 1
        }]
    )
    
    return [profile], [pub1, pub2, pub3, pub4]


@pytest.mark.asyncio
async def test_faculty_attribution(sample_data):
    profiles, pubs = sample_data
    
    mock_session = AsyncMock(spec=AsyncSession)
    
    def execute_side_effect(stmt):
        if "faculty_profiles" in str(stmt):
            mock_res = MagicMock()
            mock_res.scalars.return_value.unique.return_value.all.return_value = profiles
            return mock_res
        elif "review_tasks" in str(stmt):
            mock_res = MagicMock()
            mock_res.scalars.return_value.first.return_value = None
            return mock_res
        else:
            mock_res = MagicMock()
            mock_res.scalars.return_value.unique.return_value.all.return_value = pubs
            return mock_res
            
    mock_session.execute.side_effect = execute_side_effect
    
    agent = FacultyAttributionAgent(mock_session)
    stats = await agent.run()
    
    assert stats["processed"] == 4
    
    # pub1: High confidence (exact name + Vignan)
    # pub2: Ambiguous (J Doe, no Vignan) -> review task
    # pub3: No Match
    # pub4: High confidence (variant + VFSTR)
    
    assert stats["attributions_created"] == 2
    assert stats["high_confidence"] == 2
    assert stats["ambiguous"] == 1
    
    # Verify adds (2 pub_auths + 2 provs + 1 review task = 5 adds)
    assert mock_session.add.call_count == 5
