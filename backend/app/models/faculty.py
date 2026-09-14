"""
Faculty profile, identifiers, and name variant models.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FacultyProfile(Base):
    __tablename__ = "faculty_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # --- Original source data (preserved exactly as-is from CSV) ---
    raw_name: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_designation: Mapped[str | None] = mapped_column(String(100))
    raw_email: Mapped[str | None] = mapped_column(String(255))
    raw_phone: Mapped[str | None] = mapped_column(String(50))

    # --- Normalized identity ---
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    title_prefix: Mapped[str | None] = mapped_column(String(20))  # Dr, Mr, Ms

    # --- Institutional ---
    department: Mapped[str | None] = mapped_column(String(100), index=True)
    designation: Mapped[str | None] = mapped_column(String(100))
    institutional_email: Mapped[str | None] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(50))

    # --- Research profile ---
    research_interests: Mapped[list | None] = mapped_column(ARRAY(Text))
    education: Mapped[dict | None] = mapped_column(JSONB)
    academic_experience: Mapped[str | None] = mapped_column(Text)
    awards: Mapped[str | None] = mapped_column(Text)
    memberships: Mapped[str | None] = mapped_column(Text)
    teaching_engagements: Mapped[str | None] = mapped_column(Text)
    research_summary: Mapped[str | None] = mapped_column(Text)
    administrative_positions: Mapped[str | None] = mapped_column(Text)
    events: Mapped[str | None] = mapped_column(Text)

    # --- CSV source tracking ---
    csv_row_hash: Mapped[str | None] = mapped_column(String(64))
    source_file: Mapped[str | None] = mapped_column(String(255))
    declared_publication_count: Mapped[int | None] = mapped_column()

    # --- Status ---
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, inactive, on_leave

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # --- Relationships ---
    user = relationship("User", back_populates="faculty_profile", uselist=False)
    identifiers = relationship("FacultyIdentifier", back_populates="faculty", cascade="all, delete-orphan")
    name_variants = relationship("FacultyNameVariant", back_populates="faculty", cascade="all, delete-orphan")
    publication_links = relationship("PublicationAuthor", back_populates="faculty")
    metric_snapshots = relationship("FacultyMetricSnapshot", back_populates="faculty", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<FacultyProfile {self.raw_name} dept={self.department}>"


class FacultyIdentifier(Base):
    __tablename__ = "faculty_identifiers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    faculty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty_profiles.id"), nullable=False
    )
    identifier_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # orcid, openalex, semantic_scholar, scopus, wos, google_scholar
    identifier_value: Mapped[str] = mapped_column(String(255), nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_source: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[float | None] = mapped_column(Float)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    faculty = relationship("FacultyProfile", back_populates="identifiers")

    def __repr__(self) -> str:
        return f"<FacultyIdentifier {self.identifier_type}={self.identifier_value}>"


class FacultyNameVariant(Base):
    __tablename__ = "faculty_name_variants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    faculty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty_profiles.id"), nullable=False
    )
    name_variant: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    variant_source: Mapped[str | None] = mapped_column(String(100))  # csv_parse, publication, orcid, manual
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    faculty = relationship("FacultyProfile", back_populates="name_variants")

    def __repr__(self) -> str:
        return f"<FacultyNameVariant '{self.name_variant}'>"
