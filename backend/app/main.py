"""FastAPI application entry point.

Includes all routers under /api/v1, configures CORS, health checks,
startup/shutdown lifecycle events, and structured logging.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import api_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import async_session_factory, engine
from app.schemas.common import ErrorResponse, HealthResponse

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
setup_logging()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage startup and shutdown tasks."""
    logger.info("Application starting up")
    # Verify database connectivity on startup
    async with async_session_factory() as session:
        await session.execute(text("SELECT 1"))
    logger.info("Database connection verified")
    yield
    # Shutdown: dispose of the engine connection pool
    await engine.dispose()
    logger.info("Application shut down, database connections disposed")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
settings = get_settings()

app = FastAPI(
    title="Rental Damage Detection API",
    description="AI-powered rental equipment damage detection and tracking platform.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production via env var
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(api_router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Service health check",
)
async def health_check() -> HealthResponse:
    """Return service health status including database connectivity."""
    db_status = "ok"
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "unavailable"
        logger.warning("Health check: database unavailable")

    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        version="0.1.0",
        database=db_status,
    )
