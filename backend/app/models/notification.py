"""
Notification and NotificationPreference models for Phase 15.
Stores user and faculty research monitoring events, alerts, and user preferences.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    faculty_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty_profiles.id"), nullable=True, index=True
    )

    # Type & Category
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # verification_required, attribution_ambiguity, identity_ambiguity, integrity_warning,
    # review_task_created, review_task_resolved, metrics_updated, pipeline_completed,
    # pipeline_failed, report_generated, accreditation_updated

    category: Mapped[str] = mapped_column(String(50), default="general", index=True)
    # verification, attribution, identity, integrity, metrics, pipeline, reports, general

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="info")  # info, warning, critical, success

    # Entity Association & Provenance
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # publication, review_task, sync_run, faculty, report
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_agent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_event: Mapped[str | None] = mapped_column(String(100), nullable=True)
    action_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dedup_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    event_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Read State
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    faculty = relationship("FacultyProfile", foreign_keys=[faculty_id])

    def __repr__(self) -> str:
        return f"<Notification {self.notification_type} severity={self.severity} is_read={self.is_read}>"


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False, index=True
    )

    verification_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    integrity_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    attribution_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    identity_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    metrics_updates: Mapped[bool] = mapped_column(Boolean, default=True)
    pipeline_updates: Mapped[bool] = mapped_column(Boolean, default=True)
    report_updates: Mapped[bool] = mapped_column(Boolean, default=True)
    email_notifications: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationship
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"<NotificationPreference user_id={self.user_id}>"
