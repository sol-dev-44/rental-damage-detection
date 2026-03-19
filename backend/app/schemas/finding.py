"""Finding schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.finding import DamageSeverity, FindingStatus


class BoundingBox(BaseModel):
    """Pixel-coordinate bounding box for a detected damage region."""

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class FindingResponse(BaseModel):
    """Public representation of a damage finding."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    inspection_id: uuid.UUID
    damage_type: str
    location_description: str
    severity: DamageSeverity
    confidence_score: float
    ai_reasoning: str | None
    status: FindingStatus
    before_photo_id: uuid.UUID | None
    after_photo_id: uuid.UUID | None
    bounding_box: dict[str, Any] | None
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class FindingReview(BaseModel):
    """Schema for an operator to confirm or reject a finding."""

    status: FindingStatus = Field(
        description="New status: confirmed or rejected"
    )
    notes: str | None = Field(
        default=None, max_length=1000, description="Optional reviewer notes"
    )


class DetectionRequest(BaseModel):
    """Request body to trigger AI damage detection on an inspection."""

    before_photo_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="Photo IDs from the pre-rental inspection to use as baseline",
    )
    after_photo_ids: list[uuid.UUID] = Field(
        min_length=1,
        description="Photo IDs from the post-rental inspection to analyze",
    )


class DetectionResponse(BaseModel):
    """Response returned immediately after queueing AI detection."""

    inspection_id: uuid.UUID
    status: str = Field(
        default="analyzing",
        description="Current processing status",
    )
    estimated_completion: str = Field(
        default="30-60 seconds",
        description="Estimated time to completion",
    )
    message: str = Field(
        default="Detection task has been queued and is being processed.",
    )
