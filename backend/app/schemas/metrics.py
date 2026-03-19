"""Metrics schemas for model accuracy reporting."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AccuracyMetrics(BaseModel):
    """Overall model accuracy metrics for a time period."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    model_version: str
    period_start: datetime
    period_end: datetime
    total_inspections: int
    total_findings: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float | None
    recall: float | None
    f1_score: float | None
    avg_confidence: float | None
    severity_accuracy: dict[str, Any] | None
    damage_type_accuracy: dict[str, Any] | None
    computed_at: datetime
    tenant_id: uuid.UUID
    created_at: datetime


class DamageTypeBreakdown(BaseModel):
    """Accuracy metrics for a single damage type."""

    damage_type: str
    total: int
    true_positives: int
    false_positives: int
    precision: float | None
    avg_confidence: float | None


class AssetTypeBreakdown(BaseModel):
    """Accuracy metrics for a single asset type."""

    asset_type: str
    total_inspections: int
    total_findings: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float | None
    recall: float | None
    f1_score: float | None


class MetricsByAssetType(BaseModel):
    """Aggregated accuracy metrics broken down by asset type."""

    period_start: datetime
    period_end: datetime
    breakdowns: list[AssetTypeBreakdown]


class MetricsByDamageType(BaseModel):
    """Aggregated accuracy metrics broken down by damage type."""

    period_start: datetime
    period_end: datetime
    breakdowns: list[DamageTypeBreakdown]
