"""Shared schemas used across multiple route modules."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Query parameters for paginated list endpoints."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(
        default=20, ge=1, le=100, description="Items per page (max 100)"
    )

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    model_config = ConfigDict(from_attributes=True)

    items: list[T]
    total: int = Field(description="Total number of matching records")
    page: int = Field(description="Current page number")
    page_size: int = Field(description="Items per page")
    total_pages: int = Field(description="Total number of pages")

    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        page: int,
        page_size: int,
    ) -> PaginatedResponse[T]:
        total_pages = max(1, (total + page_size - 1) // page_size)
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )


class ErrorResponse(BaseModel):
    """Standard error response body."""

    detail: str = Field(description="Human-readable error message")
    error_code: str | None = Field(
        default=None, description="Machine-readable error code"
    )


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(default="ok", description="Service health status")
    version: str = Field(description="Application version")
    database: str = Field(description="Database connectivity status")
