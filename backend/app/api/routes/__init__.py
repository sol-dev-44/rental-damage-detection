"""Router aggregation -- include all route modules with prefixes."""

from fastapi import APIRouter

from app.api.routes.assets import router as assets_router
from app.api.routes.auth import router as auth_router
from app.api.routes.findings import router as findings_router
from app.api.routes.inspections import router as inspections_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.photos import router as photos_router
from app.api.routes.rental_sessions import router as rental_sessions_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(assets_router, prefix="/assets", tags=["assets"])
api_router.include_router(
    rental_sessions_router, prefix="/rental-sessions", tags=["rental-sessions"]
)
api_router.include_router(
    inspections_router, prefix="/inspections", tags=["inspections"]
)
api_router.include_router(photos_router, tags=["photos"])
api_router.include_router(findings_router, prefix="/findings", tags=["findings"])
api_router.include_router(metrics_router, prefix="/metrics", tags=["metrics"])
