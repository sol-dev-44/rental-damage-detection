import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import SoftDeleteMixin, TenantMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.finding import Finding
    from app.models.photo import Photo
    from app.models.rental_session import RentalSession
    from app.models.user import User


class InspectionType(str, enum.Enum):
    PRE_RENTAL = "pre_rental"
    POST_RENTAL = "post_rental"


class InspectionStatus(str, enum.Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    REVIEWED = "reviewed"
    APPROVED = "approved"


class Inspection(Base, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "inspections"

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
    rental_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rental_sessions.id"),
        nullable=True,
        index=True,
    )
    inspection_type: Mapped[InspectionType] = mapped_column(
        Enum(InspectionType, name="inspection_type", create_constraint=True),
        nullable=False,
    )
    inspector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    location_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[InspectionStatus] = mapped_column(
        Enum(InspectionStatus, name="inspection_status", create_constraint=True),
        nullable=False,
        default=InspectionStatus.PENDING,
    )

    # Relationships
    asset: Mapped["Asset"] = relationship(
        "Asset", back_populates="inspections", lazy="selectin",
    )
    rental_session: Mapped["RentalSession | None"] = relationship(
        "RentalSession",
        foreign_keys=[rental_session_id],
        lazy="selectin",
    )
    inspector: Mapped["User"] = relationship("User", lazy="selectin")
    photos: Mapped[list["Photo"]] = relationship(
        "Photo", back_populates="inspection", lazy="selectin",
    )
    findings: Mapped[list["Finding"]] = relationship(
        "Finding", back_populates="inspection", lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<Inspection id={self.id} type={self.inspection_type.value} "
            f"status={self.status.value}>"
        )
