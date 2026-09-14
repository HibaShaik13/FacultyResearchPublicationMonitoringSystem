"""
Notification API endpoints for Phase 15.
Provides listing, unread badge count, mark-as-read, and preference management.
"""

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.notification_service import NotificationService

router = APIRouter()


class NotificationPreferenceUpdate(BaseModel):
    verification_alerts: Optional[bool] = None
    integrity_alerts: Optional[bool] = None
    attribution_alerts: Optional[bool] = None
    identity_alerts: Optional[bool] = None
    metrics_updates: Optional[bool] = None
    pipeline_updates: Optional[bool] = None
    report_updates: Optional[bool] = None
    email_notifications: Optional[bool] = None


@router.get("/")
async def list_notifications(
    category: str = Query("all", description="Category filter (all, unread, verification, attribution, integrity, metrics, pipeline, reports)"),
    is_read: Optional[bool] = Query(None, description="Filter by read state"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List user notifications respecting RBAC and faculty isolation.
    """
    service = NotificationService(db)
    # Sync existing events on demand to ensure real DB records generate notifications
    await service.sync_existing_database_events()

    notifications, total = await service.get_notifications(
        current_user=current_user,
        filter_type=category,
        is_read=is_read,
        limit=limit,
        offset=offset,
    )
    unread_count = await service.get_unread_count(current_user)

    # Calculate real summary counts from the retrieved user's scope
    all_user_notifs, _ = await service.get_notifications(current_user=current_user, filter_type="all", limit=500)
    critical_count = sum(1 for n in all_user_notifs if n.severity == "critical" and not n.is_read)
    needs_review_count = sum(1 for n in all_user_notifs if n.category in ["verification", "attribution", "identity"] and not n.is_read)

    return {
        "data": [
            {
                "id": str(n.id),
                "title": n.title,
                "message": n.message,
                "notification_type": n.notification_type,
                "category": n.category,
                "severity": n.severity,
                "entity_type": n.entity_type,
                "entity_id": str(n.entity_id) if n.entity_id else None,
                "source_agent": n.source_agent,
                "source_event": n.source_event,
                "action_url": n.action_url,
                "is_read": n.is_read,
                "read_at": n.read_at.isoformat() if n.read_at else None,
                "created_at": n.created_at.isoformat() if n.created_at else None,
                "event_metadata": n.event_metadata or {},
            }
            for n in notifications
        ],
        "total": total,
        "unread_count": unread_count,
        "summary": {
            "unread": unread_count,
            "critical": critical_count,
            "needs_review": needs_review_count,
            "recent_events": total,
        },
    }


@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get live unread notifications count for the header bell badge.
    """
    service = NotificationService(db)
    # Sync events if table empty
    await service.sync_existing_database_events()
    count = await service.get_unread_count(current_user)
    return {"unread_count": count}


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a specific notification as read.
    """
    try:
        n_uuid = uuid.UUID(notification_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid notification ID format")

    service = NotificationService(db)
    notif = await service.mark_as_read(n_uuid, current_user)
    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found or access denied",
        )

    return {"message": "Notification marked as read", "id": str(notif.id), "is_read": True}


@router.post("/read-all")
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark all unread notifications for the user as read.
    """
    service = NotificationService(db)
    updated_count = await service.mark_all_as_read(current_user)
    return {"message": "All notifications marked as read", "updated_count": updated_count}


@router.get("/preferences")
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current user's notification preferences.
    """
    service = NotificationService(db)
    pref = await service.get_preferences(current_user.id)
    return {
        "verification_alerts": pref.verification_alerts,
        "integrity_alerts": pref.integrity_alerts,
        "attribution_alerts": pref.attribution_alerts,
        "identity_alerts": pref.identity_alerts,
        "metrics_updates": pref.metrics_updates,
        "pipeline_updates": pref.pipeline_updates,
        "report_updates": pref.report_updates,
        "email_notifications": pref.email_notifications,
    }


@router.put("/preferences")
async def update_preferences(
    prefs_in: NotificationPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update current user's notification preferences.
    """
    service = NotificationService(db)
    updates = {k: v for k, v in prefs_in.model_dump().items() if v is not None}
    pref = await service.update_preferences(current_user.id, updates)
    return {
        "message": "Preferences updated successfully",
        "preferences": {
            "verification_alerts": pref.verification_alerts,
            "integrity_alerts": pref.integrity_alerts,
            "attribution_alerts": pref.attribution_alerts,
            "identity_alerts": pref.identity_alerts,
            "metrics_updates": pref.metrics_updates,
            "pipeline_updates": pref.pipeline_updates,
            "report_updates": pref.report_updates,
            "email_notifications": pref.email_notifications,
        },
    }
