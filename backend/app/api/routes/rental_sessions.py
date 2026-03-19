"""Rental session routes with filters and session completion."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, get_current_user, get_pagination
from app.db.session import get_db
from app.models.asset import Asset
from app.models.rental_session import RentalSession, RentalSessionStatus
from app.models.user import User
from app.schemas.common import ErrorResponse, PaginatedResponse, PaginationParams
from app.schemas.rental_session import (
    RentalSessionCreate,
    RentalSessionResponse,
    RentalSessionUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter()


async def _get_session_or_404(
    session_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> RentalSession:
    """Retrieve a rental session or raise 404."""
    result = await db.execute(
        select(RentalSession).where(
            RentalSession.id == session_id,
            RentalSession.tenant_id == tenant_id,
            RentalSession.deleted_at.is_(None),
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rental session not found",
        )
    return session


@router.post(
    "",
    response_model=RentalSessionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Create a new rental session",
)
async def create_rental_session(
    body: RentalSessionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant)],
) -> RentalSessionResponse:
    """Create a new rental session linked to an asset."""
    # Verify asset exists and belongs to tenant
    asset_result = await db.execute(
        select(Asset).where(
            Asset.id == body.asset_id,
            Asset.tenant_id == tenant_id,
            Asset.deleted_at.is_(None),
        )
    )
    if asset_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found in this tenant",
        )

    session = RentalSession(
        asset_id=body.asset_id,
        renter_name=body.renter_name,
        renter_contact=body.renter_contact,
        started_at=body.started_at,
        notes=body.notes,
        status=RentalSessionStatus.ACTIVE,
        tenant_id=tenant_id,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    logger.info(
        "Rental session created",
        extra={"rental_session_id": session.id, "tenant_id": tenant_id},
    )
    return RentalSessionResponse.model_validate(session)


@router.get(
    "",
    response_model=PaginatedResponse[RentalSessionResponse],
    summary="List rental sessions (paginated, filterable)",
)
async def list_rental_sessions(
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    response: Response,
    session_status: RentalSessionStatus | None = Query(
        default=None, alias="status", description="Filter by session status"
    ),
    asset_id: uuid.UUID | None = Query(default=None, description="Filter by asset ID"),
    started_after: datetime | None = Query(
        default=None, description="Sessions started after this datetime"
    ),
    started_before: datetime | None = Query(
        default=None, description="Sessions started before this datetime"
    ),
) -> PaginatedResponse[RentalSessionResponse]:
    """Return a paginated, filterable list of rental sessions."""
    base_query = select(RentalSession).where(
        RentalSession.tenant_id == tenant_id,
        RentalSession.deleted_at.is_(None),
    )

    if session_status is not None:
        base_query = base_query.where(RentalSession.status == session_status)
    if asset_id is not None:
        base_query = base_query.where(RentalSession.asset_id == asset_id)
    if started_after is not None:
        base_query = base_query.where(RentalSession.started_at >= started_after)
    if started_before is not None:
        base_query = base_query.where(RentalSession.started_at <= started_before)

    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar_one()

    result = await db.execute(
        base_query.order_by(RentalSession.started_at.desc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    sessions = result.scalars().all()

    response.headers["X-RateLimit-Limit"] = "60"
    return PaginatedResponse[RentalSessionResponse].create(
        items=[RentalSessionResponse.model_validate(s) for s in sessions],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/{session_id}",
    response_model=RentalSessionResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get a single rental session",
)
async def get_rental_session(
    session_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant)],
) -> RentalSessionResponse:
    """Retrieve a single rental session by ID."""
    session = await _get_session_or_404(session_id, tenant_id, db)
    return RentalSessionResponse.model_validate(session)


@router.put(
    "/{session_id}",
    response_model=RentalSessionResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Update a rental session",
)
async def update_rental_session(
    session_id: uuid.UUID,
    body: RentalSessionUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant)],
) -> RentalSessionResponse:
    """Update fields on an existing rental session."""
    session = await _get_session_or_404(session_id, tenant_id, db)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(session, field, value)

    await db.flush()
    await db.refresh(session)

    logger.info(
        "Rental session updated",
        extra={"rental_session_id": session.id, "tenant_id": tenant_id},
    )
    return RentalSessionResponse.model_validate(session)


@router.post(
    "/{session_id}/complete",
    response_model=RentalSessionResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Mark a rental session as completed",
)
async def complete_rental_session(
    session_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant)],
) -> RentalSessionResponse:
    """Mark a rental session as completed and set ended_at to now."""
    session = await _get_session_or_404(session_id, tenant_id, db)

    if session.status != RentalSessionStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot complete session with status '{session.status.value}'",
        )

    session.status = RentalSessionStatus.COMPLETED
    session.ended_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(session)

    logger.info(
        "Rental session completed",
        extra={"rental_session_id": session.id, "tenant_id": tenant_id},
    )
    return RentalSessionResponse.model_validate(session)
