"""
Phase 15 — Notifications & Research Monitoring Test Suite.
Verifies notification service, event dispatch, RBAC, faculty isolation,
persistence, deduplication, unread counts, and preferences.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import create_app
from app.database import get_db
from app.models.user import User
from app.models.notification import Notification, NotificationPreference
from app.services.notification_service import NotificationService
from app.core.security import create_access_token


@pytest.fixture
def app_instance():
    return create_app()


@pytest.mark.asyncio
async def test_notification_creation_and_persistence():
    mock_session = AsyncMock(spec=AsyncSession)
    mock_res = MagicMock()
    mock_res.scalars.return_value.first.return_value = None
    mock_session.execute.return_value = mock_res

    service = NotificationService(mock_session)
    user_id = uuid.uuid4()
    fac_id = uuid.uuid4()

    notif = await service.create_notification(
        title="New Publication Discovered",
        message="A new publication was discovered via Crossref.",
        notification_type="publication_discovered",
        category="verification",
        severity="info",
        user_id=user_id,
        faculty_id=fac_id,
        entity_type="publication",
        entity_id=uuid.uuid4(),
        source_agent="PublicationDiscoveryAgent",
        source_event="publication_discovered",
        action_url="/publications",
        dedup_key=f"disc:{uuid.uuid4()}",
    )

    assert notif is not None
    assert notif.title == "New Publication Discovered"
    assert notif.source_agent == "PublicationDiscoveryAgent"
    assert notif.is_read is False
    assert mock_session.add.called
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_duplicate_prevention():
    mock_session = AsyncMock(spec=AsyncSession)
    existing_notif = Notification(
        id=uuid.uuid4(),
        title="Existing Event",
        message="Already recorded",
        notification_type="verification_required",
        dedup_key="unique_key_123",
        is_read=False,
    )
    mock_res = MagicMock()
    mock_res.scalars.return_value.first.return_value = existing_notif
    mock_session.execute.return_value = mock_res

    service = NotificationService(mock_session)

    result = await service.create_notification(
        title="New Event",
        message="Trying duplicate",
        notification_type="verification_required",
        dedup_key="unique_key_123",
    )

    assert result.id == existing_notif.id
    # Ensure add was NOT called because it already existed
    mock_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_unread_count_and_mark_read():
    mock_session = AsyncMock(spec=AsyncSession)
    user_id = uuid.uuid4()
    fac_id = uuid.uuid4()
    user = User(
        id=user_id,
        email="test_fac@vignan.ac.in",
        full_name="Test Faculty",
        role="faculty",
        faculty_id=fac_id,
    )

    # 1. Unread count mock
    mock_count_res = MagicMock()
    mock_count_res.scalar.return_value = 5
    mock_session.execute.return_value = mock_count_res

    service = NotificationService(mock_session)
    count = await service.get_unread_count(user)
    assert count == 5

    # 2. Mark as read
    target_notif = Notification(
        id=uuid.uuid4(),
        title="Alert",
        message="Test alert",
        notification_type="integrity_warning",
        user_id=user_id,
        faculty_id=fac_id,
        is_read=False,
    )
    mock_notif_res = MagicMock()
    mock_notif_res.scalars.return_value.first.return_value = target_notif
    mock_session.execute.return_value = mock_notif_res

    marked = await service.mark_as_read(target_notif.id, user)
    assert marked.is_read is True
    assert marked.read_at is not None
    mock_session.commit.assert_called()


@pytest.mark.asyncio
async def test_faculty_isolation():
    mock_session = AsyncMock(spec=AsyncSession)
    fac_a_id = uuid.uuid4()
    user_a = User(
        id=uuid.uuid4(),
        email="faculty_a@vignan.ac.in",
        full_name="Faculty A",
        role="faculty",
        faculty_id=fac_a_id,
    )

    notif_a = Notification(
        id=uuid.uuid4(),
        title="Faculty A Alert",
        message="Only for A",
        notification_type="attribution_ambiguity",
        faculty_id=fac_a_id,
    )

    mock_res = MagicMock()
    mock_res.scalar.return_value = 1
    mock_res.scalars.return_value.all.return_value = [notif_a]
    mock_session.execute.return_value = mock_res

    service = NotificationService(mock_session)
    notifs, total = await service.get_notifications(user_a)

    assert total == 1
    assert len(notifs) == 1
    assert notifs[0].title == "Faculty A Alert"


@pytest.mark.asyncio
async def test_admin_institutional_access():
    mock_session = AsyncMock(spec=AsyncSession)
    admin_user = User(
        id=uuid.uuid4(),
        email="admin@vignan.ac.in",
        full_name="Admin",
        role="research_admin",
        faculty_id=None,
    )

    notif_inst = Notification(
        id=uuid.uuid4(),
        title="Institutional Pipeline Sync Complete",
        message="Master sync completed across all 13 agents.",
        notification_type="pipeline_completed",
        category="pipeline",
        severity="success",
        user_id=None,
        faculty_id=None,
    )

    mock_res = MagicMock()
    mock_res.scalar.return_value = 1
    mock_res.scalars.return_value.all.return_value = [notif_inst]
    mock_session.execute.return_value = mock_res

    service = NotificationService(mock_session)
    notifs, total = await service.get_notifications(admin_user)

    assert total == 1
    assert notifs[0].title == "Institutional Pipeline Sync Complete"


@pytest.mark.asyncio
async def test_preferences_management():
    mock_session = AsyncMock(spec=AsyncSession)
    user_id = uuid.uuid4()

    mock_pref = NotificationPreference(
        id=uuid.uuid4(),
        user_id=user_id,
        verification_alerts=True,
        integrity_alerts=True,
        attribution_alerts=True,
        identity_alerts=True,
        metrics_updates=True,
        pipeline_updates=True,
        report_updates=True,
        email_notifications=False,
    )

    mock_res = MagicMock()
    mock_res.scalars.return_value.first.return_value = mock_pref
    mock_session.execute.return_value = mock_res

    service = NotificationService(mock_session)

    # Get preferences
    pref = await service.get_preferences(user_id)
    assert pref.verification_alerts is True

    # Update preferences
    updated = await service.update_preferences(
        user_id, {"integrity_alerts": False, "email_notifications": True}
    )
    assert updated.integrity_alerts is False
    assert updated.email_notifications is True
    mock_session.commit.assert_called()


@pytest.mark.asyncio
async def test_notifications_api_endpoints(app_instance):
    test_user_id = uuid.uuid4()
    fac_id = uuid.uuid4()
    user = User(
        id=test_user_id,
        email="api_test_fac@vignan.ac.in",
        full_name="API Faculty",
        role="faculty",
        faculty_id=fac_id,
        password_hash="dummy",
        is_active=True,
    )

    mock_session = AsyncMock(spec=AsyncSession)

    def execute_side_effect(stmt):
        str_stmt = str(stmt).lower()
        mock_res = MagicMock()
        if "count" in str_stmt:
            mock_res.scalar.return_value = 2
        elif "notification_preferences" in str_stmt:
            mock_res.scalars.return_value.first.return_value = NotificationPreference(
                id=uuid.uuid4(),
                user_id=test_user_id,
                verification_alerts=True,
                integrity_alerts=True,
                attribution_alerts=True,
                identity_alerts=True,
                metrics_updates=True,
                pipeline_updates=True,
                report_updates=True,
                email_notifications=False,
            )
        elif "notifications" in str_stmt:
            mock_notif = Notification(
                id=uuid.uuid4(),
                title="Review Required",
                message="DOI check needed",
                notification_type="verification_required",
                category="verification",
                severity="warning",
                faculty_id=fac_id,
                is_read=False,
                created_at=datetime.now(timezone.utc),
            )
            mock_res.scalars.return_value.all.return_value = [mock_notif]
            mock_res.scalars.return_value.first.return_value = mock_notif
        elif "users" in str_stmt:
            mock_res.scalars.return_value.first.return_value = user
        else:
            mock_res.scalar.return_value = 0
            mock_res.scalars.return_value.all.return_value = []
            mock_res.scalars.return_value.first.return_value = None
        return mock_res

    mock_session.execute.side_effect = execute_side_effect

    token = create_access_token(data={"sub": user.email, "role": user.role})
    headers = {"Authorization": f"Bearer {token}"}

    async def override_get_db():
        yield mock_session

    app_instance.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app_instance)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Unread count endpoint
        r_count = await ac.get("/api/v1/notifications/unread-count", headers=headers)
        assert r_count.status_code == 200
        assert "unread_count" in r_count.json()

        # 2. List notifications endpoint
        r_list = await ac.get("/api/v1/notifications/", headers=headers)
        assert r_list.status_code == 200
        data = r_list.json()
        assert "data" in data
        assert "summary" in data

        # 3. Preferences get & put
        r_pref = await ac.get("/api/v1/notifications/preferences", headers=headers)
        assert r_pref.status_code == 200

        r_pref_put = await ac.put(
            "/api/v1/notifications/preferences",
            headers=headers,
            json={"verification_alerts": False, "email_notifications": True},
        )
        assert r_pref_put.status_code == 200
        assert r_pref_put.json()["preferences"]["verification_alerts"] is False

    app_instance.dependency_overrides.clear()
