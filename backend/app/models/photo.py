import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.db.base import Base
from app.models.base import SoftDeleteMixin, TenantMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.inspection import Inspection


class Photo(Base, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "photos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    inspection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inspections.id"),
        nullable=False,
        index=True,
    )
    r2_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        comment="Object key in R2 — never store full URLs",
    )
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True, default=None,
        comment="Camera settings, dimensions, quality_score, etc.",
    )

    # Relationships
    inspection: Mapped["Inspection"] = relationship(
        "Inspection", back_populates="photos", lazy="selectin",
    )

    @property
    def url(self) -> str:
        """Construct the public URL at runtime from r2_key and config."""
        settings = get_settings()
        return settings.get_r2_url(self.r2_key)

    def __repr__(self) -> str:
        return f"<Photo id={self.id} r2_key={self.r2_key!r}>"
