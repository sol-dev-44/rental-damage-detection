"""Inspection routes including AI detection trigger via BackgroundTasks."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, get_current_user
from app.db.session import get_db
from app.models.asset import Asset
from app.models.inspection import Inspection, InspectionStatus
from app.models.photo import Photo
from app.models.rental_session import RentalSession
from app.models.user import User
from app.schemas.common import ErrorResponse
from app.schemas.finding import DetectionRequest, DetectionResponse
from app.schemas.inspection import InspectionCreate, InspectionResponse, InspectionUpdate

logger = logging.getLogger(__name__)

router = APIRouter()


async def _get_inspection_or_404(
    inspection_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> Inspection:
    """Retrieve an inspection or raise 404."""
    result = await db.execute(
        select(Inspection).where(
            Inspection.id == inspection_id,
            Inspection.tenant_id == tenant_id,
            Inspection.deleted_at.is_(None),
        )
    )
    inspection = result.scalar_one_or_none()
    if inspection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )
    return inspection


async def _run_detection(inspection_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    """Background task that runs AI damage detection on an inspection.

    This is a placeholder for the actual ML pipeline integration.
    In production this would call the Anthropic API with the inspection photos
    and create Finding records from the results.
    """
    from app.db.session import async_session_factory

    async with async_session_factory() as db:
        try:
            result = await db.execute(
                select(Inspection).where(Inspection.id == inspection_id)
            )
            inspection = result.scalar_one_or_none()
            if inspection is None:
                logger.error(
                    "Detection task: inspection not found",
                    extra={"inspection_id": inspection_id},
                )
                return

            # TODO: Integrate with Anthropic vision API here.
            # 1. Fetch before/after photos from R2
            # 2. Send to Claude for analysis
            # 3. Parse findings and create Finding records
            # 4. Update inspection status

            inspection.status = InspectionStatus.REVIEWED
            await db.commit()

            logger.info(
                "Detection task completed",
                extra={
                    "inspection_id": inspection_id,
                    "tenant_id": tenant_id,
                },
            )
        except Exception:
            await db.rollback()
            logger.exception(
                "Detection task failed",
                extra={"inspection_id": inspection_id},
            )


@router.post(
    "",
    response_model=InspectionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"model": ErrorResponse}},
    summary="Create a new inspection",
)
async def create_inspection(
    body: InspectionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant)],
) -> InspectionResponse:
    """Create a new inspection linked to an asset and optionally a rental session."""
    # Verify asset exists in tenant
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

    # Verify rental session if provided
    if body.rental_session_id is not None:
        rs_result = await db.execute(
            select(RentalSession).where(
                RentalSession.id == body.rental_session_id,
                RentalSession.tenant_id == tenant_id,
                RentalSession.deleted_at.is_(None),
            )
        )
        if rs_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rental session not found in this tenant",
            )

    inspection = Inspection(
        asset_id=body.asset_id,
        rental_session_id=body.rental_session_id,
        inspection_type=body.inspection_type,
        inspector_id=current_user.id,
        location_lat=body.location_lat,
        location_lng=body.location_lng,
        notes=body.notes,
        status=InspectionStatus.PENDING,
        tenant_id=tenant_id,
    )
    db.add(inspection)
    await db.flush()
    await db.refresh(inspection)

    logger.info(
        "Inspection created",
        extra={"inspection_id": inspection.id, "tenant_id": tenant_id},
    )
    return InspectionResponse.model_validate(inspection)


@router.get(
    "/{inspection_id}",
    response_model=InspectionResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get an inspection with nested photos and findings",
)
async def get_inspection(
    inspection_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant)],
) -> InspectionResponse:
    """Retrieve a single inspection including its photos and findings."""
    inspection = await _get_inspection_or_404(inspection_id, tenant_id, db)
    return InspectionResponse.model_validate(inspection)


@router.put(
    "/{inspection_id}",
    response_model=InspectionResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Update an inspection",
)
async def update_inspection(
    inspection_id: uuid.UUID,
    body: InspectionUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant)],
) -> InspectionResponse:
    """Update fields on an existing inspection."""
    inspection = await _get_inspection_or_404(inspection_id, tenant_id, db)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(inspection, field, value)

    await db.flush()
    await db.refresh(inspection)

    logger.info(
        "Inspection updated",
        extra={"inspection_id": inspection.id, "tenant_id": tenant_id},
    )
    return InspectionResponse.model_validate(inspection)


@router.post(
    "/{inspection_id}/detect",
    response_model=DetectionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Trigger AI damage detection on an inspection",
)
async def trigger_detection(
    inspection_id: uuid.UUID,
    body: DetectionRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant)],
) -> DetectionResponse:
    """Queue an AI damage detection task for the given inspection.

    The detection runs asynchronously via FastAPI BackgroundTasks. Poll the
    inspection status or use webhooks (future) to know when results are ready.
    """
    inspection = await _get_inspection_or_404(inspection_id, tenant_id, db)

    if inspection.status == InspectionStatus.ANALYZING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Detection is already in progress for this inspection",
        )

    # Validate that the referenced photos exist and belong to this tenant
    all_photo_ids = body.before_photo_ids + body.after_photo_ids
    if all_photo_ids:
        photo_result = await db.execute(
            select(Photo.id).where(
                Photo.id.in_(all_photo_ids),
                Photo.tenant_id == tenant_id,
                Photo.deleted_at.is_(None),
            )
        )
        found_ids = {row[0] for row in photo_result.all()}
        missing = set(all_photo_ids) - found_ids
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Photos not found: {[str(pid) for pid in missing]}",
            )

    # Mark inspection as analyzing
    inspection.status = InspectionStatus.ANALYZING
    await db.flush()

    # Queue background detection
    background_tasks.add_task(_run_detection, inspection_id, tenant_id)

    logger.info(
        "Detection task queued",
        extra={"inspection_id": inspection_id, "tenant_id": tenant_id},
    )
    return DetectionResponse(inspection_id=inspection_id)
