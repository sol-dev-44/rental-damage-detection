"""Full CRUD routes for assets, scoped to the authenticated tenant."""

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
from app.models.asset import Asset, AssetType
from app.models.user import User
from app.schemas.asset import AssetCreate, AssetResponse, AssetUpdate
from app.schemas.common import ErrorResponse, PaginatedResponse, PaginationParams

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}},
    summary="Create a new asset",
)
async def create_asset(
    body: AssetCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant)],
) -> AssetResponse:
    """Create a new asset within the authenticated tenant."""
    asset = Asset(
        name=body.name,
        asset_type=body.asset_type,
        identifier=body.identifier,
        metadata_=body.metadata,
        tenant_id=tenant_id,
    )
    db.add(asset)
    await db.flush()
    await db.refresh(asset)

    logger.info(
        "Asset created",
        extra={"asset_id": asset.id, "tenant_id": tenant_id},
    )
    return AssetResponse.model_validate(asset)


@router.get(
    "",
    response_model=PaginatedResponse[AssetResponse],
    summary="List assets (paginated)",
)
async def list_assets(
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    response: Response,
    asset_type: AssetType | None = Query(default=None, description="Filter by asset type"),
    search: str | None = Query(default=None, max_length=255, description="Search by name or identifier"),
) -> PaginatedResponse[AssetResponse]:
    """Return a paginated list of assets for the current tenant."""
    base_query = select(Asset).where(
        Asset.tenant_id == tenant_id,
        Asset.deleted_at.is_(None),
    )

    if asset_type is not None:
        base_query = base_query.where(Asset.asset_type == asset_type)
    if search:
        pattern = f"%{search}%"
        base_query = base_query.where(
            Asset.name.ilike(pattern) | Asset.identifier.ilike(pattern)
        )

    # Total count
    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar_one()

    # Paginated results
    result = await db.execute(
        base_query.order_by(Asset.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    assets = result.scalars().all()

    response.headers["X-RateLimit-Limit"] = "60"
    return PaginatedResponse[AssetResponse].create(
        items=[AssetResponse.model_validate(a) for a in assets],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/{asset_id}",
    response_model=AssetResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get a single asset by ID",
)
async def get_asset(
    asset_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant)],
) -> AssetResponse:
    """Retrieve a single asset, scoped to the current tenant."""
    result = await db.execute(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.tenant_id == tenant_id,
            Asset.deleted_at.is_(None),
        )
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )
    return AssetResponse.model_validate(asset)


@router.put(
    "/{asset_id}",
    response_model=AssetResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Update an asset",
)
async def update_asset(
    asset_id: uuid.UUID,
    body: AssetUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant)],
) -> AssetResponse:
    """Update fields on an existing asset."""
    result = await db.execute(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.tenant_id == tenant_id,
            Asset.deleted_at.is_(None),
        )
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    update_data = body.model_dump(exclude_unset=True)
    # Map 'metadata' field name to model's 'metadata_'
    if "metadata" in update_data:
        update_data["metadata_"] = update_data.pop("metadata")

    for field, value in update_data.items():
        setattr(asset, field, value)

    await db.flush()
    await db.refresh(asset)

    logger.info(
        "Asset updated",
        extra={"asset_id": asset.id, "tenant_id": tenant_id},
    )
    return AssetResponse.model_validate(asset)


@router.delete(
    "/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
    summary="Soft-delete an asset",
)
async def delete_asset(
    asset_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant)],
) -> None:
    """Soft-delete an asset by setting its deleted_at timestamp."""
    result = await db.execute(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.tenant_id == tenant_id,
            Asset.deleted_at.is_(None),
        )
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    asset.soft_delete()
    await db.flush()

    logger.info(
        "Asset soft-deleted",
        extra={"asset_id": asset.id, "tenant_id": tenant_id},
    )
