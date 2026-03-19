import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import SoftDeleteMixin, TenantMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.inspection import Inspection


class RentalSessionStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    DISPUTED = "disputed"


class RentalSession(Base, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "rental_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id"),
        nullable=False,
        index=True,
    )
    renter_name: Mapped[str] = mapped_column(String(255), nullable=False)
    renter_contact: Mapped[str | None] = mapped_column(String(320), nullable=True)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    status: Mapped[RentalSessionStatus] = mapped_column(
        Enum(RentalSessionStatus, name="rental_session_status", create_constraint=True),
        nullable=False,
        default=RentalSessionStatus.ACTIVE,
    )

    pre_inspection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inspections.id", use_alter=True),
        nullable=True,
    )
    post_inspection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inspections.id", use_alter=True),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    asset: Mapped["Asset"] = relationship(
        "Asset", back_populates="rental_sessions", lazy="selectin",
    )
    pre_inspection: Mapped["Inspection | None"] = relationship(
        "Inspection",
        foreign_keys=[pre_inspection_id],
        lazy="selectin",
        post_update=True,
    )
    post_inspection: Mapped["Inspection | None"] = relationship(
        "Inspection",
        foreign_keys=[post_inspection_id],
        lazy="selectin",
        post_update=True,
    )

    def __repr__(self) -> str:
        return (
            f"<RentalSession id={self.id} asset_id={self.asset_id} "
            f"status={self.status.value}>"
        )
