"""Feedback handling service.

Processes operator feedback on AI-generated findings:
  - Creates a ``Feedback`` record.
  - Updates the finding's status (confirmed / rejected).
  - Records the prediction outcome for accuracy tracking.
  - Logs the correction so it can be surfaced by the few-shot engine
    in future detection requests.

This module does NOT update the AI model itself -- there is no
fine-tuning or weight update.  Corrections are surfaced via
retrieval-augmented prompting (see ``few_shot_engine``).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml import metrics_tracker
from app.models.asset import Asset
from app.models.feedback import Feedback, FeedbackType
from app.models.finding import Finding, FindingStatus
from app.models.inspection import Inspection
from app.schemas.feedback import FeedbackCreate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _determine_finding_status(feedback_type: FeedbackType) -> FindingStatus:
    """Map a feedback type to the resulting finding status.

    TRUE_POSITIVE and SEVERITY_ADJUSTED both confirm the finding exists
    (even if severity was wrong).  FALSE_POSITIVE means the finding was
    incorrect and should be rejected.  LOCATION_CORRECTED is still a
    confirmation of the damage, just with a better location.
    """
    if feedback_type == FeedbackType.FALSE_POSITIVE:
        return FindingStatus.REJECTED
    return FindingStatus.CONFIRMED


def _was_prediction_correct(feedback_type: FeedbackType) -> bool:
    """Determine whether the original prediction was "correct" for accuracy tracking.

    For precision tracking:
      - TRUE_POSITIVE: correct
      - FALSE_POSITIVE: incorrect
      - SEVERITY_ADJUSTED: considered incorrect (severity was wrong)
      - LOCATION_CORRECTED: considered incorrect (location was wrong)
      - FALSE_NEGATIVE: N/A (not a direct feedback on an existing finding)
    """
    return feedback_type == FeedbackType.TRUE_POSITIVE


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def process_feedback(
    *,
    finding_id: uuid.UUID,
    feedback_data: FeedbackCreate,
    operator_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> Feedback:
    """Process operator feedback on a finding.

    Parameters
    ----------
    finding_id:
        The finding that the feedback applies to.
    feedback_data:
        Validated feedback payload from the API request.
    operator_id:
        The ID of the operator submitting the feedback.
    tenant_id:
        Tenant scope.
    db:
        Active async database session.

    Returns
    -------
    Feedback
        The newly created feedback record (flushed but not committed).

    Raises
    ------
    ValueError
        If the finding does not exist or does not belong to this tenant.
    """

    # -- 1. Load the finding and its inspection ----------------------------
    finding_result = await db.execute(
        select(Finding).where(
            Finding.id == finding_id,
            Finding.tenant_id == tenant_id,
            Finding.deleted_at.is_(None),
        )
    )
    finding = finding_result.scalar_one_or_none()
    if finding is None:
        raise ValueError(f"Finding {finding_id} not found")

    # Load the inspection for the feedback record.
    inspection_result = await db.execute(
        select(Inspection).where(Inspection.id == finding.inspection_id)
    )
    inspection = inspection_result.scalar_one_or_none()
    if inspection is None:
        raise ValueError(f"Inspection {finding.inspection_id} not found")

    # Load the asset for metrics recording.
    asset_result = await db.execute(
        select(Asset).where(Asset.id == inspection.asset_id)
    )
    asset = asset_result.scalar_one_or_none()

    # -- 2. Create the feedback record -------------------------------------
    feedback = Feedback(
        finding_id=finding_id,
        inspection_id=finding.inspection_id,
        feedback_type=feedback_data.feedback_type,
        operator_id=operator_id,
        operator_notes=feedback_data.operator_notes,
        corrected_damage_type=feedback_data.corrected_damage_type,
        corrected_severity=(
            feedback_data.corrected_severity.value
            if feedback_data.corrected_severity
            else None
        ),
        corrected_location=feedback_data.corrected_location,
        tenant_id=tenant_id,
    )
    db.add(feedback)

    # -- 3. Update finding status ------------------------------------------
    new_status = _determine_finding_status(feedback_data.feedback_type)
    finding.status = new_status

    await db.flush()
    await db.refresh(feedback)

    # -- 4. Record prediction outcome for accuracy tracking ----------------
    was_correct = _was_prediction_correct(feedback_data.feedback_type)

    asset_type_str = asset.asset_type.value if asset else "unknown"

    await metrics_tracker.record_prediction(
        finding_id=finding_id,
        was_correct=was_correct,
        confidence=finding.confidence_score,
        asset_type=asset_type_str,
        damage_type=finding.damage_type,
        tenant_id=tenant_id,
        db=db,
    )

    logger.info(
        "Feedback processed",
        extra={
            "feedback_id": str(feedback.id),
            "finding_id": str(finding_id),
            "feedback_type": feedback_data.feedback_type.value,
            "new_finding_status": new_status.value,
            "was_correct": was_correct,
            "tenant_id": str(tenant_id),
        },
    )

    return feedback
