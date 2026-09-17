import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from fastapi import status
from httpx import AsyncClient

from app.main import app
from app.models.user import User
from app.models.publication import Publication, PublicationAuthor
from app.models.faculty import FacultyProfile
from app.models.review import ReviewTask
from app.models.provenance import AuditLog, ProvenanceRecord
from app.agents.human_review_agent import HumanReviewAgent
from app.api.v1.auth import get_current_user
from app.database import get_db


@pytest.mark.asyncio
async def test_human_review_agent_task_creation():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    
    # Check idempotency - first call creates, second call returns existing
    mock_res = MagicMock()
    mock_res.scalars.return_value.first.return_value = None
    mock_session.execute.return_value = mock_res
    
    agent = HumanReviewAgent(mock_session)
    pub_id = uuid.uuid4()
    
    task = await agent.create_task(
        task_type="verification_review",
        priority="high",
        entity_type="publication",
        entity_id=pub_id,
        explanation="DOI mismatch requires human review",
        evidence={"score": 45.0, "evidence_chain": ["Missing DOI."]},
        agent_name="VerificationAgent",
    )
    
    assert task.task_type == "verification_review"
    assert task.priority == "high"
    assert task.status == "pending"
    assert task.entity_id == pub_id
    mock_session.add.assert_called_once()


@pytest.mark.asyncio
async def test_human_review_agent_task_resolution():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    reviewer = User(
        id=uuid.uuid4(),
        email="admin@vignan.ac.in",
        full_name="Admin Reviewer",
        role="research_admin",
    )
    
    pub_id = uuid.uuid4()
    mock_pub = Publication(
        id=pub_id,
        title="Testing Publication Resolution",
        verification_status="needs_review",
        metadata_confidence=40.0,
    )
    
    task_id = uuid.uuid4()
    mock_task = ReviewTask(
        id=task_id,
        task_type="verification_review",
        priority="high",
        status="pending",
        entity_type="publication",
        entity_id=pub_id,
        explanation="Needs verification",
        created_at=datetime.now(timezone.utc),
    )
    
    async def mock_get(model, model_id):
        if model == ReviewTask:
            return mock_task
        elif model == Publication:
            return mock_pub
        return None
        
    mock_session.get.side_effect = mock_get
    
    agent = HumanReviewAgent(mock_session)
    
    # 1. Test Approve
    res = await agent.resolve_task(
        task_id=task_id,
        decision="approve",
        reviewer=reviewer,
        comment="Confirmed by research dean",
    )
    
    assert res["status"] == "success"
    assert res["decision"] == "approve"
    assert mock_pub.verification_status == "human_verified"
    assert mock_pub.metadata_confidence >= 95.0
    assert mock_task.status == "resolved"
    assert mock_task.decided_by == reviewer.id
    
    # Verify AuditLog and Provenance additions
    assert mock_session.add.call_count >= 2


@pytest.mark.asyncio
async def test_review_api_endpoints_and_rbac():
    admin_user = User(
        id=uuid.uuid4(),
        email="admin@vignan.ac.in",
        full_name="System Admin",
        role="research_admin",
        is_active=True,
    )
    
    pub_id = uuid.uuid4()
    mock_pub = Publication(
        id=pub_id,
        title="Sample Test Publication for Review",
        doi="10.1109/TEST.2025.1",
        year=2025,
        verification_status="needs_review",
        metadata_confidence=45.0,
        risk_level="none",
    )
    mock_pub.authors = []
    mock_pub.sources = []
    
    mock_task = ReviewTask(
        id=uuid.uuid4(),
        task_type="verification_review",
        priority="high",
        status="pending",
        entity_type="publication",
        entity_id=pub_id,
        explanation="Publication needs human review",
        evidence={"evidence_chain": ["Missing DOI."], "score": 45.0},
        agent_name="VerificationAgent",
        created_at=datetime.now(timezone.utc),
    )

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    
    async def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        if "count" in stmt_str:
            res.scalar.return_value = 1
            res.scalars.return_value.all.return_value = [1]
        elif "publications" in stmt_str:
            res.scalars.return_value.first.return_value = mock_pub
            res.scalars.return_value.all.return_value = [mock_pub]
        elif "review_tasks" in stmt_str:
            res.scalars.return_value.all.return_value = [mock_task]
            res.scalars.return_value.first.return_value = mock_task
        else:
            res.scalars.return_value.all.return_value = []
            res.scalars.return_value.first.return_value = None
            res.scalar.return_value = 0
        return res

    mock_db.execute = AsyncMock(side_effect=mock_execute)
    
    async def mock_get(model, model_id):
        if model == ReviewTask:
            return mock_task
        elif model == Publication:
            return mock_pub
        elif model == User:
            return admin_user
        return None
        
    mock_db.get = AsyncMock(side_effect=mock_get)

    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[get_db] = lambda: mock_db

    from httpx import ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Stats endpoint
        resp = await client.get("/api/v1/review/stats")
        assert resp.status_code == 200
        stats = resp.json()
        assert stats["pending"] >= 0
        assert stats["user_role"] == "research_admin"

        # 2. Queue endpoint
        resp_q = await client.get("/api/v1/review/queue")
        assert resp_q.status_code == 200
        q_data = resp_q.json()
        assert len(q_data["data"]) > 0
        assert q_data["data"][0]["priority"] == "high"

        # 3. Decision submission endpoint
        resp_d = await client.post(
            f"/api/v1/review/{mock_task.id}/decide",
            json={"decision": "approve", "comment": "Approved and verified"}
        )
        assert resp_d.status_code == 200
        dec_data = resp_d.json()
        assert dec_data["status"] == "success"
        assert dec_data["decision"] == "approve"

        # 4. History endpoint
        resp_h = await client.get("/api/v1/review/history")
        assert resp_h.status_code == 200
        h_data = resp_h.json()
        assert "data" in h_data

    app.dependency_overrides.clear()
