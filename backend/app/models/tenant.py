import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class Tenant(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    settings: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=None)
    subscription_tier: Mapped[str] = mapped_column(
        String(50), nullable=False, default="free"
    )

    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="tenant", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Tenant id={self.id} slug={self.slug!r}>"
