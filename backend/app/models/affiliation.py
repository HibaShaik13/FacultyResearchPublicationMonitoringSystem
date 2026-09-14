"""
Affiliation variant model for institutional affiliation intelligence.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AffiliationVariant(Base):
    __tablename__ = "affiliation_variants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    canonical_name: Mapped[str] = mapped_column(String(500), nullable=False)
    variant_text: Mapped[str] = mapped_column(String(500), nullable=False)
    variant_normalized: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, index=True)
    department: Mapped[str | None] = mapped_column(String(100))
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str | None] = mapped_column(String(100))  # seed, discovered, manual
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<AffiliationVariant '{self.variant_text[:50]}'>"
