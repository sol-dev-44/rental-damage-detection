import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TenantMixin, TimestampMixin


class ModelMetrics(Base, TimestampMixin, TenantMixin):
    __tablename__ = "model_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    model_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Identifier for the Anthropic model or prompt version used",
    )
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )

    total_inspections: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_findings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    true_positives: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    false_positives: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    false_negatives: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    precision: Mapped[float | None] = mapped_column(Float, nullable=True)
    recall: Mapped[float | None] = mapped_column(Float, nullable=True)
    f1_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    severity_accuracy: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, default=None,
        comment="Breakdown of accuracy per severity level",
    )
    damage_type_accuracy: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, default=None,
        comment="Breakdown of accuracy per damage type",
    )

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<ModelMetrics id={self.id} version={self.model_version!r} "
            f"f1={self.f1_score}>"
        )
