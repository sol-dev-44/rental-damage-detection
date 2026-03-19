"""Pytest fixtures for the rental-damage-detection test suite.

Key design decisions:
  - Uses SQLite async (aiosqlite) as the test database so tests can run
    without a PostgreSQL server.
  - Provides factory fixtures for creating test data (tenants, users,
    assets, inspections, photos, findings).
  - Provides an ``AsyncClient`` fixture for integration tests against
    the FastAPI app.
  - Mocks the Claude API so tests never make real API calls.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# ---------------------------------------------------------------------------
# Override settings BEFORE any app imports so the app sees test config.
# ---------------------------------------------------------------------------
import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["R2_ACCOUNT_ID"] = "test-account"
os.environ["R2_ACCESS_KEY_ID"] = "test-key"
os.environ["R2_SECRET_ACCESS_KEY"] = "test-secret"
os.environ["R2_BUCKET_NAME"] = "test-bucket"
os.environ["R2_PUBLIC_URL"] = "https://test-cdn.example.com"
os.environ["ANTHROPIC_API_KEY"] = "test-anthropic-key"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret"

from app.db.base import Base
from app.models.asset import Asset, AssetType
from app.models.feedback import Feedback, FeedbackType
from app.models.finding import DamageSeverity, Finding, FindingStatus
from app.models.inspection import Inspection, InspectionStatus, InspectionType
from app.models.photo import Photo
from app.models.rental_session import RentalSession, RentalSessionStatus
from app.models.repair_cost import RepairCostLookup
from app.models.tenant import Tenant
from app.models.user import User, UserRole


# ---------------------------------------------------------------------------
# Database engine + session fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_engine():
    """Create an in-memory SQLite async engine and set up all tables."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # SQLite needs foreign key enforcement enabled per-connection.
    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fk(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide an async session for a single test, rolled back afterwards."""
    session_factory = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# FastAPI test client
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an httpx AsyncClient wired to the FastAPI app.

    The ``get_db`` dependency is overridden to use the test session so
    all requests share the same transactional scope.
    """
    from app.db.session import get_db
    from app.main import app

    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Factory fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_tenant(db: AsyncSession) -> Tenant:
    """Create and return a test tenant."""
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Test Marina",
        slug="test-marina",
        subscription_tier="pro",
    )
    db.add(tenant)
    await db.flush()
    return tenant


@pytest_asyncio.fixture
async def test_user(db: AsyncSession, test_tenant: Tenant) -> User:
    """Create and return a test user within the test tenant."""
    user = User(
        id=uuid.uuid4(),
        email="operator@test-marina.com",
        hashed_password="$2b$12$fakehashfortest",
        full_name="Test Operator",
        role=UserRole.OPERATOR,
        tenant_id=test_tenant.id,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def test_asset(db: AsyncSession, test_tenant: Tenant) -> Asset:
    """Create and return a test jetski asset."""
    asset = Asset(
        id=uuid.uuid4(),
        name="WaveRunner EX",
        asset_type=AssetType.JETSKI,
        identifier="HIN-123456",
        metadata_={"year": 2023, "make": "Yamaha", "model": "EX"},
        tenant_id=test_tenant.id,
    )
    db.add(asset)
    await db.flush()
    return asset


@pytest_asyncio.fixture
async def test_inspection(
    db: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
    test_asset: Asset,
) -> Inspection:
    """Create and return a test post-rental inspection."""
    inspection = Inspection(
        id=uuid.uuid4(),
        asset_id=test_asset.id,
        inspection_type=InspectionType.POST_RENTAL,
        inspector_id=test_user.id,
        status=InspectionStatus.PENDING,
        tenant_id=test_tenant.id,
    )
    db.add(inspection)
    await db.flush()
    return inspection


@pytest_asyncio.fixture
async def test_photo(
    db: AsyncSession,
    test_tenant: Tenant,
    test_inspection: Inspection,
) -> Photo:
    """Create and return a test photo record."""
    photo = Photo(
        id=uuid.uuid4(),
        inspection_id=test_inspection.id,
        r2_key=f"{test_tenant.id}/{test_inspection.id}/test-photo.jpg",
        sequence_order=0,
        original_filename="test-photo.jpg",
        content_type="image/jpeg",
        file_size_bytes=1024 * 500,
        tenant_id=test_tenant.id,
    )
    db.add(photo)
    await db.flush()
    return photo


@pytest_asyncio.fixture
async def test_finding(
    db: AsyncSession,
    test_tenant: Tenant,
    test_inspection: Inspection,
) -> Finding:
    """Create and return a test finding."""
    finding = Finding(
        id=uuid.uuid4(),
        inspection_id=test_inspection.id,
        damage_type="scratch",
        location_description="Starboard hull, midship",
        severity=DamageSeverity.MODERATE,
        confidence_score=85.0,
        ai_reasoning="Visible scratch mark not present in before photos",
        status=FindingStatus.PENDING,
        tenant_id=test_tenant.id,
    )
    db.add(finding)
    await db.flush()
    return finding


# ---------------------------------------------------------------------------
# Mock Claude API fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_claude_response() -> dict[str, Any]:
    """Return a realistic Claude API response dict."""
    return {
        "findings": [
            {
                "damage_type": "scratch",
                "location_description": "Port side hull near waterline",
                "severity": "moderate",
                "confidence_score": 82,
                "ai_reasoning": "Linear mark approximately 15cm long visible in after photo, not present in before photo.",
                "bounding_box": {"x": 120, "y": 300, "width": 200, "height": 40},
            },
            {
                "damage_type": "dent",
                "location_description": "Bow area, above waterline",
                "severity": "minor",
                "confidence_score": 75,
                "ai_reasoning": "Small indentation consistent with minor impact.",
                "bounding_box": None,
            },
        ],
    }


@pytest.fixture
def mock_claude_client(mock_claude_response):
    """Patch the Claude client to return a canned response without making API calls."""
    from app.ml.claude_client import ClaudeVisionResult

    mock_result = ClaudeVisionResult(
        parsed_json=mock_claude_response,
        raw_text='{"findings": []}',
        input_tokens=5000,
        output_tokens=500,
        estimated_cost_usd=0.0225,
        model="claude-sonnet-4-20250514",
        duration_seconds=3.5,
    )

    with patch("app.ml.claude_client.send_vision_request", return_value=mock_result) as mock:
        yield mock
