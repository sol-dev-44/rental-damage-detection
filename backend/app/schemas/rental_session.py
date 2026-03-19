"""Rental session schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.rental_session import RentalSessionStatus


class InspectionSummary(BaseModel):
    """Lightweight inspection reference embedded in rental session responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    inspection_type: str
    status: str
    timestamp: datetime


class RentalSessionCreate(BaseModel):
    """Schema for creating a new rental session."""

    asset_id: uuid.UUID
    renter_name: str = Field(min_length=1, max_length=255)
    renter_contact: str | None = Field(default=None, max_length=320)
    started_at: datetime
    notes: str | None = None


class RentalSessionUpdate(BaseModel):
    """Schema for updating a rental session. All fields optional."""

    renter_name: str | None = Field(default=None, min_length=1, max_length=255)
    renter_contact: str | None = Field(default=None, max_length=320)
    ended_at: datetime | None = None
    status: RentalSessionStatus | None = None
    notes: str | None = None
    pre_inspection_id: uuid.UUID | None = None
    post_inspection_id: uuid.UUID | None = None


class RentalSessionResponse(BaseModel):
    """Public representation of a rental session."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asset_id: uuid.UUID
    renter_name: str
    renter_contact: str | None
    started_at: datetime
    ended_at: datetime | None
    status: RentalSessionStatus
    pre_inspection_id: uuid.UUID | None
    post_inspection_id: uuid.UUID | None
    pre_inspection: InspectionSummary | None = None
    post_inspection: InspectionSummary | None = None
    notes: str | None
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
