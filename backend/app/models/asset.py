import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import SoftDeleteMixin, TenantMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.inspection import Inspection
    from app.models.rental_session import RentalSession


class AssetType(str, enum.Enum):
    JETSKI = "jetski"
    BOAT = "boat"
    PARASAIL = "parasail"
    OTHER = "other"


class Asset(Base, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[AssetType] = mapped_column(
        Enum(AssetType, name="asset_type", create_constraint=True),
        nullable=False,
    )
    identifier: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True,
        comment="Hull number, registration, serial, etc.",
    )
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True, default=None,
        comment="Arbitrary equipment metadata (year, make, model, colour, etc.)",
    )

    # Relationships
    rental_sessions: Mapped[list["RentalSession"]] = relationship(
        "RentalSession", back_populates="asset", lazy="selectin",
    )
    inspections: Mapped[list["Inspection"]] = relationship(
        "Inspection", back_populates="asset", lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Asset id={self.id} name={self.name!r} type={self.asset_type.value}>"
