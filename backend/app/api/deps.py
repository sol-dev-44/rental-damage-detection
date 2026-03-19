"""Shared FastAPI dependencies for authentication, tenancy, and pagination."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_token
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.common import PaginationParams

bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Decode JWT, look up the user, and verify they are not soft-deleted."""
    try:
        payload = verify_token(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(
        select(User).where(
            User.id == payload.user_id,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or has been deactivated",
        )

    return user


async def get_current_tenant(
    user: Annotated[User, Depends(get_current_user)],
) -> uuid.UUID:
    """Extract the tenant_id from the authenticated user."""
    return user.tenant_id


def require_role(*allowed_roles: UserRole):
    """Dependency factory that restricts access to users with specific roles.

    Usage::

        @router.post("/admin-only", dependencies=[Depends(require_role(UserRole.ADMIN))])
        async def admin_endpoint(): ...
    """

    async def _check_role(
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role.value}' is not authorized for this action",
            )
        return user

    return _check_role


def get_pagination(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(
        default=20, ge=1, le=100, description="Items per page (max 100)"
    ),
) -> PaginationParams:
    """Parse and validate pagination query parameters."""
    return PaginationParams(page=page, page_size=page_size)
