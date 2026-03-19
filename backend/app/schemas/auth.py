"""Authentication and user schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import UserRole


class LoginRequest(BaseModel):
    """Credentials for obtaining an access token."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    """JWT token response returned after successful authentication."""

    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    """Schema for registering a new user."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    role: UserRole = Field(default=UserRole.OPERATOR)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserResponse(BaseModel):
    """Public representation of a user."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
