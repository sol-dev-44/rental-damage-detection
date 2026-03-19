from sqlalchemy.ext.asyncio import AsyncAttrs, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


def create_engine():
    """Create the async SQLAlchemy engine using application settings."""
    settings = get_settings()
    return create_async_engine(
        settings.DATABASE_URL,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_POOL_SIZE,
        pool_pre_ping=True,
        echo=False,
    )
