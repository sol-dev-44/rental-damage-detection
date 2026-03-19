"""Photo routes: upload to inspections, retrieve, and delete."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.inspection import Inspection
from app.models.photo import Photo
from app.models.user import User
from app.schemas.common import ErrorResponse
from app.schemas.photo import PhotoResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/inspections/{inspection_id}/photos",
    response_model=PhotoResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
    },
    summary="Upload a photo to an inspection",
)
async def upload_photo(
    inspection_id: uuid.UUID,
    file: UploadFile,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant)],
) -> PhotoResponse:
    """Upload a photo file and associate it with an inspection.

    Validates file type and size constraints. The file is stored in R2 and
    only the object key is persisted in the database.
    """
    settings = get_settings()

    # Verify inspection exists and belongs to tenant
    insp_result = await db.execute(
        select(Inspection).where(
            Inspection.id == inspection_id,
            Inspection.tenant_id == tenant_id,
            Inspection.deleted_at.is_(None),
        )
    )
    if insp_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found in this tenant",
        )

    # Validate content type
    if file.content_type not in settings.ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported image type '{file.content_type}'. "
                f"Allowed: {settings.ALLOWED_IMAGE_TYPES}"
            ),
        )

    # Read file and validate size
    content = await file.read()
    if len(content) > settings.max_photo_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.MAX_PHOTO_SIZE_MB}MB",
        )

    # Determine next sequence order for this inspection
    seq_result = await db.execute(
        select(func.coalesce(func.max(Photo.sequence_order), -1)).where(
            Photo.inspection_id == inspection_id,
            Photo.deleted_at.is_(None),
        )
    )
    next_order = seq_result.scalar_one() + 1

    # Generate R2 key
    photo_id = uuid.uuid4()
    extension = (file.filename or "photo.jpg").rsplit(".", 1)[-1]
    r2_key = f"tenants/{tenant_id}/inspections/{inspection_id}/{photo_id}.{extension}"

    # TODO: Upload content to R2 via boto3/aioboto3
    # async with get_r2_client() as client:
    #     await client.put_object(
    #         Bucket=settings.R2_BUCKET_NAME, Key=r2_key, Body=content,
    #         ContentType=file.content_type,
    #     )

    photo = Photo(
        id=photo_id,
        inspection_id=inspection_id,
        r2_key=r2_key,
        sequence_order=next_order,
        original_filename=file.filename or "unknown",
        content_type=file.content_type or "application/octet-stream",
        file_size_bytes=len(content),
        tenant_id=tenant_id,
    )
    db.add(photo)
    await db.flush()
    await db.refresh(photo)

    logger.info(
        "Photo uploaded",
        extra={
            "photo_id": photo.id,
            "inspection_id": inspection_id,
            "tenant_id": tenant_id,
        },
    )
    return PhotoResponse.model_validate(photo)


@router.get(
    "/photos/{photo_id}",
    response_model=PhotoResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get a single photo by ID",
)
async def get_photo(
    photo_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant)],
) -> PhotoResponse:
    """Retrieve metadata for a single photo, including its constructed URL."""
    result = await db.execute(
        select(Photo).where(
            Photo.id == photo_id,
            Photo.tenant_id == tenant_id,
            Photo.deleted_at.is_(None),
        )
    )
    photo = result.scalar_one_or_none()
    if photo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found",
        )
    return PhotoResponse.model_validate(photo)


@router.delete(
    "/photos/{photo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
    summary="Soft-delete a photo",
)
async def delete_photo(
    photo_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant)],
) -> None:
    """Soft-delete a photo. The R2 object is retained for audit purposes."""
    result = await db.execute(
        select(Photo).where(
            Photo.id == photo_id,
            Photo.tenant_id == tenant_id,
            Photo.deleted_at.is_(None),
        )
    )
    photo = result.scalar_one_or_none()
    if photo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found",
        )

    photo.soft_delete()
    await db.flush()

    logger.info(
        "Photo soft-deleted",
        extra={"photo_id": photo.id, "tenant_id": tenant_id},
    )
