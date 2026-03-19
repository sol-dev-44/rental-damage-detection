"""Inspection schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.inspection import InspectionStatus, InspectionType


class PhotoSummary(BaseModel):
    """Lightweight photo reference embedded in inspection responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    url: str
    sequence_order: int
    original_filename: str
    content_type: str


class FindingSummary(BaseModel):
    """Lightweight finding reference embedded in inspection responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    damage_type: str
    severity: str
    confidence_score: float
    status: str


class InspectionCreate(BaseModel):
    """Schema for creating a new inspection."""

    asset_id: uuid.UUID
    rental_session_id: uuid.UUID | None = None
    inspection_type: InspectionType
    location_lat: float | None = Field(default=None, ge=-90, le=90)
    location_lng: float | None = Field(default=None, ge=-180, le=180)
    notes: str | None = None


class InspectionUpdate(BaseModel):
    """Schema for updating an inspection. All fields optional."""

    status: InspectionStatus | None = None
    location_lat: float | None = Field(default=None, ge=-90, le=90)
    location_lng: float | None = Field(default=None, ge=-180, le=180)
    notes: str | None = None


class InspectionResponse(BaseModel):
    """Public representation of an inspection with nested photo and finding summaries."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asset_id: uuid.UUID
    rental_session_id: uuid.UUID | None
    inspection_type: InspectionType
    inspector_id: uuid.UUID
    timestamp: datetime
    location_lat: float | None
    location_lng: float | None
    notes: str | None
    status: InspectionStatus
    photos: list[PhotoSummary] = Field(default_factory=list)
    findings: list[FindingSummary] = Field(default_factory=list)
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
