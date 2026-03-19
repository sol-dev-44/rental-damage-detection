import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import SoftDeleteMixin, TenantMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.finding import Finding
    from app.models.inspection import Inspection
    from app.models.user import User


class FeedbackType(str, enum.Enum):
    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"
    SEVERITY_ADJUSTED = "severity_adjusted"
    LOCATION_CORRECTED = "location_corrected"


class Feedback(Base, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("findings.id"),
        nullable=False,
        index=True,
    )
    inspection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inspections.id"),
        nullable=False,
        index=True,
    )
    feedback_type: Mapped[FeedbackType] = mapped_column(
        Enum(FeedbackType, name="feedback_type", create_constraint=True),
        nullable=False,
    )
    operator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    operator_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_damage_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    corrected_severity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    corrected_location: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    finding: Mapped["Finding"] = relationship(
        "Finding", back_populates="feedback", lazy="selectin",
    )
    inspection: Mapped["Inspection"] = relationship("Inspection", lazy="selectin")
    operator: Mapped["User"] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<Feedback id={self.id} type={self.feedback_type.value} "
            f"finding_id={self.finding_id}>"
        )
