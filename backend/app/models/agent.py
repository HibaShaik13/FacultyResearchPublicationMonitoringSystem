"""
Sync run and agent run models for pipeline execution tracking.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SyncRun(Base):
    """Tracks a complete synchronization cycle."""
    __tablename__ = "sync_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # full_sync, citation_refresh, manual, csv_import
    status: Mapped[str] = mapped_column(String(20), default="running")
    # running, completed, failed, paused
    trigger: Mapped[str | None] = mapped_column(String(50))  # scheduled, manual, api
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )

    # --- Stats ---
    publications_discovered: Mapped[int] = mapped_column(Integer, default=0)
    publications_merged: Mapped[int] = mapped_column(Integer, default=0)
    publications_verified: Mapped[int] = mapped_column(Integer, default=0)
    review_tasks_created: Mapped[int] = mapped_column(Integer, default=0)
    errors_count: Mapped[int] = mapped_column(Integer, default=0)

    # --- Timing ---
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    agent_runs = relationship("AgentRun", back_populates="sync_run", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<SyncRun {self.run_type} status={self.status}>"


class AgentRun(Base):
    """Tracks individual agent execution within a sync run."""
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sync_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sync_runs.id"), index=True
    )
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="running")
    # running, completed, failed, skipped

    # --- I/O tracking ---
    input_count: Mapped[int | None] = mapped_column(Integer)
    output_count: Mapped[int | None] = mapped_column(Integer)
    error_count: Mapped[int] = mapped_column(Integer, default=0)

    # --- Timing ---
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    # --- Details ---
    config: Mapped[dict | None] = mapped_column(JSONB)
    errors: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    sync_run = relationship("SyncRun", back_populates="agent_runs")

    def __repr__(self) -> str:
        return f"<AgentRun {self.agent_name} status={self.status}>"
