"""
Review task model for human-in-the-loop verification.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReviewTask(Base):
    __tablename__ = "review_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # attribution_ambiguous, duplicate_uncertain, affiliation_conflict,
    # risk_flag, metadata_conflict, identifier_match, missing_faculty
    priority: Mapped[str] = mapped_column(String(10), default="medium")  # low, medium, high, critical
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    # pending, in_review, resolved, deferred

    # --- Context ---
    entity_type: Mapped[str | None] = mapped_column(String(50))  # publication, faculty
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    related_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # --- Evidence ---
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict | None] = mapped_column(JSONB)
    options: Mapped[dict | None] = mapped_column(JSONB)

    # --- Assignment ---
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- Resolution ---
    decision: Mapped[str | None] = mapped_column(String(50))
    # confirm, reject, merge, reassign, defer, split
    decision_detail: Mapped[dict | None] = mapped_column(JSONB)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- Metadata ---
    agent_name: Mapped[str | None] = mapped_column(String(100))
    sync_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sync_runs.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<ReviewTask {self.task_type} status={self.status} priority={self.priority}>"
