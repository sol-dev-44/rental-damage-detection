"""Few-shot example retrieval via metadata-based filtering.

Retrieves past operator corrections (from the ``feedback`` table) that
match the asset type and, optionally, specific damage types.  These
examples are injected into the prompt to help Claude avoid repeating
known mistakes.

This is *retrieval-augmented prompting*, NOT "learning".  Claude has no
persistent memory -- we simply surface relevant historical corrections
as in-context examples each time a new detection request is made.

Implementation note: NO vector similarity / CLIP embeddings / pgvector.
Filtering is purely on discrete metadata columns (asset_type, damage_type).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback import Feedback, FeedbackType
from app.models.finding import Finding
from app.models.inspection import Inspection
from app.models.asset import Asset

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_similar_cases(
    *,
    asset_type: str,
    damage_types: list[str] | None = None,
    tenant_id: uuid.UUID,
    limit: int = 5,
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """Return formatted few-shot examples for the prompt builder.

    The query joins ``feedback -> finding -> inspection -> asset`` and
    filters on:
      - ``asset.asset_type`` matches the target asset type.
      - ``feedback.feedback_type`` is an actionable correction
        (``FALSE_POSITIVE``, ``SEVERITY_ADJUSTED``, ``LOCATION_CORRECTED``).
      - Optionally, ``finding.damage_type`` overlaps with *damage_types*.
      - ``feedback.tenant_id`` matches (tenant isolation).

    Results are ordered by recency (most recent corrections first) so the
    model sees the freshest operator intent.

    Parameters
    ----------
    asset_type:
        The ``AssetType`` enum value (e.g. ``"jetski"``).
    damage_types:
        Optional list of damage type strings to prioritise.  If provided,
        matching rows are returned first, followed by other corrections
        for the same asset type up to *limit*.
    tenant_id:
        Tenant scope -- only corrections from this tenant are returned.
    limit:
        Maximum number of examples to return.
    db:
        An active async database session.

    Returns
    -------
    list[dict[str, Any]]
        Each dict contains the keys expected by ``prompt_builder``:
        ``original_damage_type``, ``original_severity``, ``feedback_type``,
        ``corrected_damage_type``, ``corrected_severity``, ``operator_notes``.
    """

    # Only consider correction-type feedback (not TRUE_POSITIVE confirmations).
    correction_types = [
        FeedbackType.FALSE_POSITIVE,
        FeedbackType.SEVERITY_ADJUSTED,
        FeedbackType.LOCATION_CORRECTED,
    ]

    stmt = (
        select(
            Finding.damage_type,
            Finding.severity,
            Finding.confidence_score,
            Feedback.feedback_type,
            Feedback.corrected_damage_type,
            Feedback.corrected_severity,
            Feedback.corrected_location,
            Feedback.operator_notes,
            Feedback.created_at,
        )
        .join(Finding, Feedback.finding_id == Finding.id)
        .join(Inspection, Finding.inspection_id == Inspection.id)
        .join(Asset, Inspection.asset_id == Asset.id)
        .where(
            Feedback.tenant_id == tenant_id,
            Feedback.deleted_at.is_(None),
            Finding.deleted_at.is_(None),
            Asset.asset_type == asset_type,
            Feedback.feedback_type.in_(correction_types),
        )
    )

    # If specific damage types are requested, add an optional filter but
    # still allow other asset-type matches to fill the remaining slots.
    if damage_types:
        # Prioritise rows where the finding damage_type matches, but do not
        # exclude others -- we sort matching rows first via a CASE expression.
        from sqlalchemy import case, literal

        priority = case(
            (Finding.damage_type.in_(damage_types), literal(0)),
            else_=literal(1),
        )
        stmt = stmt.order_by(priority, desc(Feedback.created_at))
    else:
        stmt = stmt.order_by(desc(Feedback.created_at))

    stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    rows = result.all()

    examples: list[dict[str, Any]] = []
    for row in rows:
        examples.append({
            "original_damage_type": row.damage_type,
            "original_severity": row.severity.value if hasattr(row.severity, "value") else str(row.severity),
            "original_confidence": row.confidence_score,
            "feedback_type": row.feedback_type.value if hasattr(row.feedback_type, "value") else str(row.feedback_type),
            "corrected_damage_type": row.corrected_damage_type,
            "corrected_severity": row.corrected_severity,
            "corrected_location": row.corrected_location,
            "operator_notes": row.operator_notes,
        })

    logger.info(
        "Few-shot examples retrieved",
        extra={
            "asset_type": asset_type,
            "tenant_id": str(tenant_id),
            "num_examples": len(examples),
        },
    )

    return examples
