"""Photo schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.core.config import get_settings


class PhotoMetadata(BaseModel):
    """Metadata associated with an uploaded photo."""

    width: int | None = None
    height: int | None = None
    quality_score: float | None = Field(
        default=None, ge=0, le=100, description="Image quality score 0-100"
    )
    camera_settings: dict[str, Any] | None = None


class PhotoResponse(BaseModel):
    """Public representation of a photo. URL is constructed from the stored R2 key."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    inspection_id: uuid.UUID
    r2_key: str
    sequence_order: int
    original_filename: str
    content_type: str
    file_size_bytes: int
    metadata: dict[str, Any] | None = Field(
        default=None, validation_alias="metadata_"
    )
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def url(self) -> str:
        """Construct the public URL at runtime from r2_key and config."""
        settings = get_settings()
        return settings.get_r2_url(self.r2_key)
