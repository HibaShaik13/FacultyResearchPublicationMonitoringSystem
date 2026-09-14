"""
Citation and faculty metric snapshot models for historical tracking.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CitationSnapshot(Base):
    __tablename__ = "citation_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    publication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    citation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    # openalex, semantic_scholar, crossref
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    publication = relationship("Publication", back_populates="citation_snapshots")

    def __repr__(self) -> str:
        return f"<CitationSnapshot pub={self.publication_id} count={self.citation_count} date={self.snapshot_date}>"


class FacultyMetricSnapshot(Base):
    __tablename__ = "faculty_metric_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    faculty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty_profiles.id"), nullable=False, index=True
    )
    h_index: Mapped[int] = mapped_column(Integer, default=0)
    i10_index: Mapped[int] = mapped_column(Integer, default=0)
    total_citations: Mapped[int] = mapped_column(Integer, default=0)
    total_publications: Mapped[int] = mapped_column(Integer, default=0)
    verified_publications: Mapped[int] = mapped_column(Integer, default=0)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    faculty = relationship("FacultyProfile", back_populates="metric_snapshots")

    def __repr__(self) -> str:
        return f"<FacultyMetricSnapshot faculty={self.faculty_id} h={self.h_index} date={self.snapshot_date}>"
