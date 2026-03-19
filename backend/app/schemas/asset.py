"""Asset schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.asset import AssetType


class AssetCreate(BaseModel):
    """Schema for creating a new asset."""

    name: str = Field(min_length=1, max_length=255)
    asset_type: AssetType
    identifier: str = Field(
        min_length=1,
        max_length=100,
        description="Hull number, registration, serial, etc.",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Arbitrary equipment metadata (year, make, model, colour, etc.)",
    )


class AssetUpdate(BaseModel):
    """Schema for updating an existing asset. All fields optional."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    asset_type: AssetType | None = None
    identifier: str | None = Field(default=None, min_length=1, max_length=100)
    metadata: dict[str, Any] | None = None


class AssetResponse(BaseModel):
    """Public representation of an asset."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    asset_type: AssetType
    identifier: str
    metadata: dict[str, Any] | None = Field(
        default=None, validation_alias="metadata_"
    )
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
