import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.publication import Publication, PublicationSource, PublicationAuthor
from app.models.review import ReviewTask
from app.agents.verification_agent import VerificationAgent

@pytest.fixture
def sample_publications():
    # 1. Fully verified: DOI + multiple sources + high attribution confidence + no risk
    pub1 = Publication(id=uuid.uuid4(), title="Fully Verified", doi="10.123/1", risk_level="none", verification_status="pending", metadata_confidence=0.0)
    src1_a = PublicationSource(publication_id=pub1.id, source_system="openalex")
    src1_b = PublicationSource(publication_id=pub1.id, source_system="crossref")
    pub1.sources = [src1_a, src1_b]
    auth1 = PublicationAuthor(publication_id=pub1.id, faculty_id=uuid.uuid4(), attribution_confidence=0.90)
    pub1.authors = [auth1]

    # 2. Partially verified: DOI + single source + low attribution confidence + no risk
    pub2 = Publication(id=uuid.uuid4(), title="Partially Verified", doi="10.123/2", risk_level="none", verification_status="pending", metadata_confidence=0.0)
    src2 = PublicationSource(publication_id=pub2.id, source_system="openalex")
    pub2.sources = [src2]
    auth2 = PublicationAuthor(publication_id=pub2.id, faculty_id=uuid.uuid4(), attribution_confidence=0.70)
    pub2.authors = [auth2]

    # 3. Needs review: DOI + multiple sources + missing faculty attribution + no risk
    pub3 = Publication(id=uuid.uuid4(), title="Needs Review", doi="10.123/3", risk_level="none", verification_status="pending", metadata_confidence=0.0)
    src3_a = PublicationSource(publication_id=pub3.id, source_system="openalex")
    src3_b = PublicationSource(publication_id=pub3.id, source_system="crossref")
    pub3.sources = [src3_a, src3_b]
    pub3.authors = []

    # 4. Rejected: HIGH risk
    pub4 = Publication(id=uuid.uuid4(), title="Rejected", doi="10.123/4", risk_level="high", verification_status="pending", metadata_confidence=0.0)
    src4 = PublicationSource(publication_id=pub4.id, source_system="openalex")
    pub4.sources = [src4]
    pub4.authors = []

    # 5. Rejected (No sources)
    pub5 = Publication(id=uuid.uuid4(), title="No sources", doi="10.123/5", risk_level="none", verification_status="pending", metadata_confidence=0.0)
    pub5.sources = []
    pub5.authors = []

    return [pub1, pub2, pub3, pub4, pub5]


@pytest.mark.asyncio
async def test_verification_agent(sample_publications):
    mock_session = AsyncMock(spec=AsyncSession)
    
    def execute_side_effect(stmt):
        stmt_str = str(stmt).lower()
        if "review_tasks" in stmt_str:
            mock_res = MagicMock()
            mock_res.scalars.return_value.first.return_value = None
            return mock_res
        else:
            mock_res = MagicMock()
            mock_res.scalars.return_value.unique.return_value.all.return_value = sample_publications
            return mock_res
            
    mock_session.execute.side_effect = execute_side_effect
    
    agent = VerificationAgent(mock_session)
    stats = await agent.run()
    
    assert stats["processed"] == 5
    
    # 1. Fully verified
    assert sample_publications[0].verification_status == "verified"
    
    # 2. Partially verified
    assert sample_publications[1].verification_status == "partially_verified"
    
    # 3. Needs review
    assert sample_publications[2].verification_status == "needs_review"
    
    # 4. Rejected
    assert sample_publications[3].verification_status == "rejected"
    
    # 5. Rejected (no sources)
    assert sample_publications[4].verification_status == "rejected"
    
    assert stats["verified"] == 1
    assert stats["partially_verified"] == 1
    assert stats["needs_review"] == 1
    assert stats["rejected"] == 2
    
    # 3 review tasks (for needs_review, rejected, rejected)
    assert stats["review_tasks"] == 3
    
    # 5 evidence records
    assert stats["evidence_records"] == 5
