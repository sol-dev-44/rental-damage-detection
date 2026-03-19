"""Authentication routes: login, register, and current-user retrieval."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, TokenResponse, UserCreate, UserResponse
from app.schemas.common import ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse}},
    summary="Authenticate and obtain a JWT",
)
async def login(
    body: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Validate credentials and return a JWT access token."""
    result = await db.execute(
        select(User).where(User.email == body.email, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role.value,
    )
    logger.info(
        "User logged in",
        extra={"user_id": user.id, "tenant_id": user.tenant_id},
    )
    return TokenResponse(access_token=token)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Register a new user (admin only)",
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def register(
    body: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Create a new user within the current tenant. Only admins may call this."""
    # Check for duplicate email
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists",
        )

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
        tenant_id=current_user.tenant_id,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    logger.info(
        "User registered",
        extra={
            "user_id": user.id,
            "tenant_id": user.tenant_id,
            "created_by": current_user.id,
        },
    )
    return UserResponse.model_validate(user)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the current authenticated user",
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Return the profile of the currently authenticated user."""
    return UserResponse.model_validate(current_user)
