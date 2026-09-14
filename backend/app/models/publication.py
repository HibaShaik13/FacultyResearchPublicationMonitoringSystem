"""
Publication, publication-author link, and publication source models.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Publication(Base):
    __tablename__ = "publications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # --- Identity ---
    title: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_title: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    doi: Mapped[str | None] = mapped_column(String(255), index=True)

    # --- Metadata ---
    authors_raw: Mapped[str | None] = mapped_column(Text)
    authors_parsed: Mapped[dict | None] = mapped_column(JSONB)  # [{name, affiliation, position}]
    publication_date: Mapped[date | None] = mapped_column(Date)
    year: Mapped[int | None] = mapped_column(Integer, index=True)
    month: Mapped[int | None] = mapped_column(Integer)

    # --- Venue ---
    journal_name: Mapped[str | None] = mapped_column(String(500))
    conference_name: Mapped[str | None] = mapped_column(String(500))
    publisher: Mapped[str | None] = mapped_column(String(255))
    volume: Mapped[str | None] = mapped_column(String(50))
    issue: Mapped[str | None] = mapped_column(String(50))
    pages: Mapped[str | None] = mapped_column(String(50))
    issn: Mapped[str | None] = mapped_column(String(20))

    # --- Classification ---
    publication_type: Mapped[str | None] = mapped_column(String(50))
    # journal-article, conference-paper, book-chapter, preprint, thesis, patent, report, other

    # --- Content ---
    abstract: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[list | None] = mapped_column(ARRAY(Text))

    # --- Affiliation ---
    affiliation_text: Mapped[str | None] = mapped_column(Text)
    affiliation_normalized: Mapped[str | None] = mapped_column(Text)
    affiliation_match_confidence: Mapped[float | None] = mapped_column(Float)

    # --- Quality metrics ---
    indexing_status: Mapped[list | None] = mapped_column(ARRAY(Text))  # ['SCIE', 'Scopus']
    quartile: Mapped[str | None] = mapped_column(String(10))  # Q1-Q4
    impact_factor: Mapped[float | None] = mapped_column(Float)
    citescore: Mapped[float | None] = mapped_column(Float)
    open_access: Mapped[bool | None] = mapped_column(Boolean)

    # --- Citations (latest) ---
    citation_count: Mapped[int] = mapped_column(Integer, default=0)
    citation_source: Mapped[str | None] = mapped_column(String(50))

    # --- Verification ---
    verification_status: Mapped[str] = mapped_column(
        String(30), default="pending", index=True
    )
    # pending, auto_verified, review_required, human_verified, human_rejected, human_corrected, conflict
    attribution_confidence: Mapped[float | None] = mapped_column(Float)
    metadata_confidence: Mapped[float | None] = mapped_column(Float)

    # --- Risk ---
    risk_level: Mapped[str] = mapped_column(String(10), default="none", index=True)
    # none, low, medium, high
    risk_reasons: Mapped[dict | None] = mapped_column(JSONB)

    # --- Source tracking ---
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_csv_text: Mapped[str | None] = mapped_column(Text)  # Original CSV text if from CSV import

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # --- Relationships ---
    authors = relationship("PublicationAuthor", back_populates="publication", cascade="all, delete-orphan")
    sources = relationship("PublicationSource", back_populates="publication", cascade="all, delete-orphan")
    citation_snapshots = relationship("CitationSnapshot", back_populates="publication", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Publication '{self.title[:60]}' ({self.year})>"


class PublicationAuthor(Base):
    __tablename__ = "publication_authors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    publication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    faculty_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty_profiles.id"), index=True
    )
    author_position: Mapped[int | None] = mapped_column(Integer)
    author_name_raw: Mapped[str | None] = mapped_column(String(255))
    attribution_confidence: Mapped[float | None] = mapped_column(Float)
    attribution_method: Mapped[str | None] = mapped_column(String(100))
    is_corresponding: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    publication = relationship("Publication", back_populates="authors")
    faculty = relationship("FacultyProfile", back_populates="publication_links")

    def __repr__(self) -> str:
        return f"<PublicationAuthor pub={self.publication_id} faculty={self.faculty_id}>"


class PublicationSource(Base):
    __tablename__ = "publication_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    publication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)
    # openalex, crossref, semantic_scholar, orcid, csv_import, manual
    source_id: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(Text)
    raw_metadata: Mapped[dict | None] = mapped_column(JSONB)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    discovery_method: Mapped[str | None] = mapped_column(String(100))
    sync_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sync_runs.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    publication = relationship("Publication", back_populates="sources")

    def __repr__(self) -> str:
        return f"<PublicationSource {self.source_system}:{self.source_id}>"
