"""Feedback schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.feedback import FeedbackType
from app.models.finding import DamageSeverity


class FeedbackCreate(BaseModel):
    """Schema for submitting operator feedback on a finding."""

    feedback_type: FeedbackType
    operator_notes: str | None = Field(default=None, max_length=2000)
    corrected_damage_type: str | None = Field(default=None, max_length=100)
    corrected_severity: DamageSeverity | None = None
    corrected_location: str | None = Field(default=None, max_length=500)


class FeedbackResponse(BaseModel):
    """Public representation of operator feedback."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    finding_id: uuid.UUID
    inspection_id: uuid.UUID
    feedback_type: FeedbackType
    operator_id: uuid.UUID
    operator_notes: str | None
    corrected_damage_type: str | None
    corrected_severity: str | None
    corrected_location: str | None
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
