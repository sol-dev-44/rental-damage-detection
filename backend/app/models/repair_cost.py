import uuid

from sqlalchemy import Float, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import SoftDeleteMixin, TenantMixin, TimestampMixin


class RepairCostLookup(Base, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "repair_cost_lookups"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "asset_type", "damage_type", "severity",
            name="uq_repair_cost_lookup",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    asset_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Matches AssetType enum values: jetski, boat, parasail, other",
    )
    damage_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="e.g. scratch, dent, crack, tear",
    )
    severity: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Matches DamageSeverity enum values: minor, moderate, major, severe",
    )

    min_cost: Mapped[float] = mapped_column(Float, nullable=False)
    max_cost: Mapped[float] = mapped_column(Float, nullable=False)
    avg_cost: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    def __repr__(self) -> str:
        return (
            f"<RepairCostLookup id={self.id} "
            f"{self.asset_type}/{self.damage_type}/{self.severity} "
            f"avg={self.avg_cost} {self.currency}>"
        )
