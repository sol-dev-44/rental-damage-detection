"""Metrics routes for model accuracy reporting."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, get_current_user
from app.db.session import get_db
from app.models.model_metrics import ModelMetrics
from app.models.user import User
from app.schemas.common import ErrorResponse
from app.schemas.metrics import AccuracyMetrics, MetricsByAssetType, MetricsByDamageType

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/accuracy",
    response_model=AccuracyMetrics,
    responses={404: {"model": ErrorResponse}},
    summary="Get overall model accuracy metrics",
)
async def get_accuracy_metrics(
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant)],
    response: Response,
    model_version: str | None = Query(
        default=None, description="Filter by model version"
    ),
) -> AccuracyMetrics:
    """Return the most recent overall accuracy metrics for the tenant.

    Optionally filter by model version. Returns the latest computed metrics.
    """
    query = (
        select(ModelMetrics)
        .where(ModelMetrics.tenant_id == tenant_id)
        .order_by(ModelMetrics.computed_at.desc())
    )
    if model_version is not None:
        query = query.where(ModelMetrics.model_version == model_version)

    result = await db.execute(query.limit(1))
    metrics = result.scalar_one_or_none()

    if metrics is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No metrics data available for this tenant",
        )

    response.headers["X-RateLimit-Limit"] = "60"
    return AccuracyMetrics.model_validate(metrics)


@router.get(
    "/by-asset-type",
    response_model=MetricsByAssetType,
    responses={404: {"model": ErrorResponse}},
    summary="Get accuracy metrics broken down by asset type",
)
async def get_metrics_by_asset_type(
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant)],
    response: Response,
) -> MetricsByAssetType:
    """Return the latest metrics with a per-asset-type breakdown.

    The breakdown is extracted from the damage_type_accuracy JSONB field of the
    most recent ModelMetrics record. This endpoint assumes that the metrics
    computation job populates asset-type breakdowns in severity_accuracy.
    """
    query = (
        select(ModelMetrics)
        .where(ModelMetrics.tenant_id == tenant_id)
        .order_by(ModelMetrics.computed_at.desc())
        .limit(1)
    )
    result = await db.execute(query)
    metrics = result.scalar_one_or_none()

    if metrics is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No metrics data available for this tenant",
        )

    # Extract per-asset-type breakdowns from severity_accuracy JSONB
    breakdowns = []
    raw = metrics.severity_accuracy or {}
    for asset_type, data in raw.items():
        if isinstance(data, dict):
            breakdowns.append(
                {
                    "asset_type": asset_type,
                    "total_inspections": data.get("total_inspections", 0),
                    "total_findings": data.get("total_findings", 0),
                    "true_positives": data.get("true_positives", 0),
                    "false_positives": data.get("false_positives", 0),
                    "false_negatives": data.get("false_negatives", 0),
                    "precision": data.get("precision"),
                    "recall": data.get("recall"),
                    "f1_score": data.get("f1_score"),
                }
            )

    response.headers["X-RateLimit-Limit"] = "60"
    return MetricsByAssetType(
        period_start=metrics.period_start,
        period_end=metrics.period_end,
        breakdowns=breakdowns,
    )


@router.get(
    "/by-damage-type",
    response_model=MetricsByDamageType,
    responses={404: {"model": ErrorResponse}},
    summary="Get accuracy metrics broken down by damage type",
)
async def get_metrics_by_damage_type(
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant)],
    response: Response,
) -> MetricsByDamageType:
    """Return the latest metrics with a per-damage-type breakdown.

    The breakdown is extracted from the damage_type_accuracy JSONB field.
    """
    query = (
        select(ModelMetrics)
        .where(ModelMetrics.tenant_id == tenant_id)
        .order_by(ModelMetrics.computed_at.desc())
        .limit(1)
    )
    result = await db.execute(query)
    metrics = result.scalar_one_or_none()

    if metrics is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No metrics data available for this tenant",
        )

    # Extract per-damage-type breakdowns from damage_type_accuracy JSONB
    breakdowns = []
    raw = metrics.damage_type_accuracy or {}
    for damage_type, data in raw.items():
        if isinstance(data, dict):
            breakdowns.append(
                {
                    "damage_type": damage_type,
                    "total": data.get("total", 0),
                    "true_positives": data.get("true_positives", 0),
                    "false_positives": data.get("false_positives", 0),
                    "precision": data.get("precision"),
                    "avg_confidence": data.get("avg_confidence"),
                }
            )

    response.headers["X-RateLimit-Limit"] = "60"
    return MetricsByDamageType(
        period_start=metrics.period_start,
        period_end=metrics.period_end,
        breakdowns=breakdowns,
    )
