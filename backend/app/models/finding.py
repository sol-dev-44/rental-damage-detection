import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import SoftDeleteMixin, TenantMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.feedback import Feedback
    from app.models.inspection import Inspection
    from app.models.photo import Photo


class DamageSeverity(str, enum.Enum):
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    SEVERE = "severe"


class FindingStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class Finding(Base, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "findings"

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
    damage_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="e.g. scratch, dent, crack, tear, discoloration",
    )
    location_description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Human-readable location of the damage on the asset",
    )
    severity: Mapped[DamageSeverity] = mapped_column(
        Enum(DamageSeverity, name="damage_severity", create_constraint=True),
        nullable=False,
    )
    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="AI confidence 0-100",
    )
    ai_reasoning: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Explanation from the AI model about the finding",
    )
    status: Mapped[FindingStatus] = mapped_column(
        Enum(FindingStatus, name="finding_status", create_constraint=True),
        nullable=False,
        default=FindingStatus.PENDING,
    )

    before_photo_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("photos.id"),
        nullable=True,
    )
    after_photo_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("photos.id"),
        nullable=True,
    )

    bounding_box: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment='{"x": int, "y": int, "width": int, "height": int} in pixels',
    )

    # Relationships
    inspection: Mapped["Inspection"] = relationship(
        "Inspection", back_populates="findings", lazy="selectin",
    )
    before_photo: Mapped["Photo | None"] = relationship(
        "Photo", foreign_keys=[before_photo_id], lazy="selectin",
    )
    after_photo: Mapped["Photo | None"] = relationship(
        "Photo", foreign_keys=[after_photo_id], lazy="selectin",
    )
    feedback: Mapped[list["Feedback"]] = relationship(
        "Feedback", back_populates="finding", lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<Finding id={self.id} type={self.damage_type!r} "
            f"severity={self.severity.value} confidence={self.confidence_score}>"
        )
