"""Finding routes: retrieval, operator review, and feedback submission."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, get_current_user, require_role
from app.db.session import get_db
from app.models.feedback import Feedback
from app.models.finding import Finding, FindingStatus
from app.models.user import User, UserRole
from app.schemas.common import ErrorResponse
from app.schemas.feedback import FeedbackCreate, FeedbackResponse
from app.schemas.finding import FindingResponse, FindingReview

logger = logging.getLogger(__name__)

router = APIRouter()


async def _get_finding_or_404(
    finding_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> Finding:
    """Retrieve a finding or raise 404."""
    result = await db.execute(
        select(Finding).where(
            Finding.id == finding_id,
            Finding.tenant_id == tenant_id,
            Finding.deleted_at.is_(None),
        )
    )
    finding = result.scalar_one_or_none()
    if finding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finding not found",
        )
    return finding


@router.get(
    "/{finding_id}",
    response_model=FindingResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get a single finding by ID",
)
async def get_finding(
    finding_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant)],
) -> FindingResponse:
    """Retrieve a single damage finding."""
    finding = await _get_finding_or_404(finding_id, tenant_id, db)
    return FindingResponse.model_validate(finding)


@router.put(
    "/{finding_id}/review",
    response_model=FindingResponse,
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Confirm or reject a finding (operator review)",
    dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR))],
)
async def review_finding(
    finding_id: uuid.UUID,
    body: FindingReview,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant)],
) -> FindingResponse:
    """Allow an operator or admin to confirm or reject an AI-generated finding."""
    finding = await _get_finding_or_404(finding_id, tenant_id, db)

    if body.status not in (FindingStatus.CONFIRMED, FindingStatus.REJECTED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Review status must be 'confirmed' or 'rejected'",
        )

    if finding.status != FindingStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Finding has already been reviewed (status: {finding.status.value})",
        )

    finding.status = body.status
    await db.flush()
    await db.refresh(finding)

    logger.info(
        "Finding reviewed",
        extra={
            "finding_id": finding.id,
            "status": body.status.value,
            "reviewer_id": current_user.id,
            "tenant_id": tenant_id,
        },
    )
    return FindingResponse.model_validate(finding)


@router.post(
    "/{finding_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Submit operator correction feedback on a finding",
    dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR))],
)
async def submit_feedback(
    finding_id: uuid.UUID,
    body: FeedbackCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant)],
) -> FeedbackResponse:
    """Submit correction feedback for a damage finding to improve future AI accuracy."""
    finding = await _get_finding_or_404(finding_id, tenant_id, db)

    feedback = Feedback(
        finding_id=finding.id,
        inspection_id=finding.inspection_id,
        feedback_type=body.feedback_type,
        operator_id=current_user.id,
        operator_notes=body.operator_notes,
        corrected_damage_type=body.corrected_damage_type,
        corrected_severity=body.corrected_severity.value if body.corrected_severity else None,
        corrected_location=body.corrected_location,
        tenant_id=tenant_id,
    )
    db.add(feedback)
    await db.flush()
    await db.refresh(feedback)

    logger.info(
        "Feedback submitted",
        extra={
            "feedback_id": feedback.id,
            "finding_id": finding_id,
            "tenant_id": tenant_id,
        },
    )
    return FeedbackResponse.model_validate(feedback)
