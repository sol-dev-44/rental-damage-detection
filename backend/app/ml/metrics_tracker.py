"""Accuracy tracking for damage-detection predictions.

Provides functions to record individual prediction outcomes and query
aggregate accuracy metrics, broken down by asset type, damage type,
and confidence band.

Note on confidence calibration: Claude's confidence scores are NOT
inherently calibrated.  A score of 80 does not mean 80% probability
of correctness.  This module tracks *empirical* accuracy per
confidence band so operators and downstream logic can assess how
reliable a given confidence level actually is.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, case, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback import Feedback, FeedbackType
from app.models.finding import Finding
from app.models.inspection import Inspection
from app.models.asset import Asset

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Confidence bands for calibration analysis.
# Each band is (lower_inclusive, upper_exclusive, label).
# ---------------------------------------------------------------------------
CONFIDENCE_BANDS: list[tuple[float, float, str]] = [
    (0, 50, "0-49"),
    (50, 70, "50-69"),
    (70, 85, "70-84"),
    (85, 101, "85-100"),  # 101 to include 100
]


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------

async def record_prediction(
    *,
    finding_id: uuid.UUID,
    was_correct: bool,
    confidence: float,
    asset_type: str,
    damage_type: str,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Record the outcome of a single prediction for later aggregation.

    This is called by the feedback processor when an operator confirms
    or rejects a finding.  The actual accuracy statistics are computed
    on-the-fly from the ``feedback`` table, so this function currently
    only logs.  A future iteration may write to a dedicated
    ``prediction_outcomes`` table for faster queries on large datasets.
    """
    logger.info(
        "Prediction outcome recorded",
        extra={
            "finding_id": str(finding_id),
            "was_correct": was_correct,
            "confidence": confidence,
            "asset_type": asset_type,
            "damage_type": damage_type,
            "tenant_id": str(tenant_id),
        },
    )


# ---------------------------------------------------------------------------
# Aggregate queries
# ---------------------------------------------------------------------------

def _build_base_query(tenant_id: uuid.UUID):
    """Common base: join feedback -> finding -> inspection -> asset, scoped to tenant."""
    return (
        select(
            Finding.damage_type,
            Finding.confidence_score,
            Finding.severity,
            Feedback.feedback_type,
            Asset.asset_type,
        )
        .join(Finding, Feedback.finding_id == Finding.id)
        .join(Inspection, Finding.inspection_id == Inspection.id)
        .join(Asset, Inspection.asset_id == Asset.id)
        .where(
            Feedback.tenant_id == tenant_id,
            Feedback.deleted_at.is_(None),
            Finding.deleted_at.is_(None),
        )
    )


async def get_accuracy_by_asset_type(
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> dict[str, dict[str, Any]]:
    """Return accuracy metrics grouped by asset type.

    Returns a dict like::

        {
            "jetski": {"total": 50, "correct": 42, "accuracy": 0.84},
            "boat":   {"total": 30, "correct": 27, "accuracy": 0.90},
        }
    """
    correct_case = case(
        (Feedback.feedback_type == FeedbackType.TRUE_POSITIVE, literal(1)),
        else_=literal(0),
    )

    stmt = (
        select(
            Asset.asset_type,
            func.count().label("total"),
            func.sum(correct_case).label("correct"),
        )
        .select_from(Feedback)
        .join(Finding, Feedback.finding_id == Finding.id)
        .join(Inspection, Finding.inspection_id == Inspection.id)
        .join(Asset, Inspection.asset_id == Asset.id)
        .where(
            Feedback.tenant_id == tenant_id,
            Feedback.deleted_at.is_(None),
            Finding.deleted_at.is_(None),
            Feedback.feedback_type.in_([
                FeedbackType.TRUE_POSITIVE,
                FeedbackType.FALSE_POSITIVE,
            ]),
        )
        .group_by(Asset.asset_type)
    )

    result = await db.execute(stmt)
    rows = result.all()

    metrics: dict[str, dict[str, Any]] = {}
    for row in rows:
        at = row.asset_type.value if hasattr(row.asset_type, "value") else str(row.asset_type)
        total = row.total
        correct = row.correct or 0
        metrics[at] = {
            "total": total,
            "correct": correct,
            "accuracy": round(correct / total, 4) if total > 0 else 0.0,
        }
    return metrics


async def get_accuracy_by_damage_type(
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> dict[str, dict[str, Any]]:
    """Return accuracy metrics grouped by damage type.

    Same shape as ``get_accuracy_by_asset_type`` but keyed on
    ``finding.damage_type`` instead.
    """
    correct_case = case(
        (Feedback.feedback_type == FeedbackType.TRUE_POSITIVE, literal(1)),
        else_=literal(0),
    )

    stmt = (
        select(
            Finding.damage_type,
            func.count().label("total"),
            func.sum(correct_case).label("correct"),
        )
        .select_from(Feedback)
        .join(Finding, Feedback.finding_id == Finding.id)
        .where(
            Feedback.tenant_id == tenant_id,
            Feedback.deleted_at.is_(None),
            Finding.deleted_at.is_(None),
            Feedback.feedback_type.in_([
                FeedbackType.TRUE_POSITIVE,
                FeedbackType.FALSE_POSITIVE,
            ]),
        )
        .group_by(Finding.damage_type)
    )

    result = await db.execute(stmt)
    rows = result.all()

    metrics: dict[str, dict[str, Any]] = {}
    for row in rows:
        total = row.total
        correct = row.correct or 0
        metrics[row.damage_type] = {
            "total": total,
            "correct": correct,
            "accuracy": round(correct / total, 4) if total > 0 else 0.0,
        }
    return metrics


async def get_confidence_calibration(
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> dict[str, dict[str, Any]]:
    """Track empirical accuracy per confidence band.

    Claude's confidence scores are not inherently calibrated.  This
    function measures how often predictions within each band are
    actually correct, so operators can gauge trustworthiness.

    Returns::

        {
            "0-49":  {"total": 10, "correct": 3, "accuracy": 0.30},
            "50-69": {"total": 20, "correct": 12, "accuracy": 0.60},
            "70-84": {"total": 35, "correct": 28, "accuracy": 0.80},
            "85-100":{"total": 40, "correct": 37, "accuracy": 0.925},
        }
    """
    # We need individual rows to bucket by confidence, so fetch them all
    # for this tenant.  For tenants with very large feedback volumes a
    # pre-aggregated table would be more efficient.
    stmt = (
        select(
            Finding.confidence_score,
            Feedback.feedback_type,
        )
        .select_from(Feedback)
        .join(Finding, Feedback.finding_id == Finding.id)
        .where(
            Feedback.tenant_id == tenant_id,
            Feedback.deleted_at.is_(None),
            Finding.deleted_at.is_(None),
            Feedback.feedback_type.in_([
                FeedbackType.TRUE_POSITIVE,
                FeedbackType.FALSE_POSITIVE,
            ]),
        )
    )

    result = await db.execute(stmt)
    rows = result.all()

    # Initialise buckets.
    buckets: dict[str, dict[str, int]] = {
        label: {"total": 0, "correct": 0} for _, _, label in CONFIDENCE_BANDS
    }

    for row in rows:
        conf = row.confidence_score
        is_correct = row.feedback_type == FeedbackType.TRUE_POSITIVE
        for lo, hi, label in CONFIDENCE_BANDS:
            if lo <= conf < hi:
                buckets[label]["total"] += 1
                if is_correct:
                    buckets[label]["correct"] += 1
                break

    calibration: dict[str, dict[str, Any]] = {}
    for label, counts in buckets.items():
        total = counts["total"]
        correct = counts["correct"]
        calibration[label] = {
            "total": total,
            "correct": correct,
            "accuracy": round(correct / total, 4) if total > 0 else 0.0,
        }

    return calibration


async def get_overall_accuracy(
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> dict[str, Any]:
    """Return overall accuracy summary for a tenant.

    Returns::

        {
            "total_reviewed": 100,
            "true_positives": 75,
            "false_positives": 25,
            "precision": 0.75,
        }
    """
    tp_case = case(
        (Feedback.feedback_type == FeedbackType.TRUE_POSITIVE, literal(1)),
        else_=literal(0),
    )
    fp_case = case(
        (Feedback.feedback_type == FeedbackType.FALSE_POSITIVE, literal(1)),
        else_=literal(0),
    )

    stmt = (
        select(
            func.count().label("total"),
            func.sum(tp_case).label("tp"),
            func.sum(fp_case).label("fp"),
        )
        .select_from(Feedback)
        .join(Finding, Feedback.finding_id == Finding.id)
        .where(
            Feedback.tenant_id == tenant_id,
            Feedback.deleted_at.is_(None),
            Finding.deleted_at.is_(None),
            Feedback.feedback_type.in_([
                FeedbackType.TRUE_POSITIVE,
                FeedbackType.FALSE_POSITIVE,
            ]),
        )
    )

    result = await db.execute(stmt)
    row = result.one()

    total = row.total or 0
    tp = row.tp or 0
    fp = row.fp or 0

    return {
        "total_reviewed": total,
        "true_positives": tp,
        "false_positives": fp,
        "precision": round(tp / total, 4) if total > 0 else 0.0,
    }
