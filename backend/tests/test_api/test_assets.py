"""Tests for the assets CRUD API endpoints.

Covers:
  - Create, list, get, update, soft-delete.
  - Tenant isolation (cannot see another tenant's assets).
  - Pagination.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset, AssetType
from app.models.tenant import Tenant
from app.models.user import User, UserRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_headers(user_id: uuid.UUID, tenant_id: uuid.UUID) -> dict[str, str]:
    """Return a Bearer header with a mocked JWT payload."""
    # We patch verify_token in the tests that need auth.
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def _patch_auth(test_user):
    """Patch the auth dependency to return the test user."""
    from app.api.deps import get_current_user, get_current_tenant

    async def _override_user():
        return test_user

    async def _override_tenant():
        return test_user.tenant_id

    from app.main import app

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_tenant] = _override_tenant
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_tenant, None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCreateAsset:
    """POST /api/v1/assets"""

    async def test_create_asset_success(
        self, client: AsyncClient, _patch_auth, test_tenant: Tenant
    ):
        payload = {
            "name": "Sea Doo Spark",
            "asset_type": "jetski",
            "identifier": "HIN-999",
            "metadata": {"year": 2024, "color": "blue"},
        }
        resp = await client.post(
            "/api/v1/assets", json=payload, headers=_auth_headers(uuid.uuid4(), test_tenant.id)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Sea Doo Spark"
        assert data["asset_type"] == "jetski"
        assert data["identifier"] == "HIN-999"
        assert data["tenant_id"] == str(test_tenant.id)
        assert "id" in data

    async def test_create_asset_missing_name(
        self, client: AsyncClient, _patch_auth, test_tenant: Tenant
    ):
        payload = {"asset_type": "boat", "identifier": "REG-001"}
        resp = await client.post(
            "/api/v1/assets", json=payload, headers=_auth_headers(uuid.uuid4(), test_tenant.id)
        )
        assert resp.status_code == 422


class TestListAssets:
    """GET /api/v1/assets"""

    async def test_list_empty(self, client: AsyncClient, _patch_auth):
        resp = await client.get(
            "/api/v1/assets", headers=_auth_headers(uuid.uuid4(), uuid.uuid4())
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_with_assets(
        self,
        client: AsyncClient,
        _patch_auth,
        test_asset: Asset,
    ):
        resp = await client.get(
            "/api/v1/assets", headers=_auth_headers(uuid.uuid4(), uuid.uuid4())
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        names = [item["name"] for item in data["items"]]
        assert test_asset.name in names

    async def test_list_pagination(
        self,
        client: AsyncClient,
        db: AsyncSession,
        _patch_auth,
        test_tenant: Tenant,
    ):
        # Create 5 assets.
        for i in range(5):
            asset = Asset(
                name=f"Asset {i}",
                asset_type=AssetType.BOAT,
                identifier=f"BOAT-{i:03d}",
                tenant_id=test_tenant.id,
            )
            db.add(asset)
        await db.flush()

        # Page 1, size 2.
        resp = await client.get(
            "/api/v1/assets?page=1&page_size=2",
            headers=_auth_headers(uuid.uuid4(), uuid.uuid4()),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["total_pages"] == 3

    async def test_list_filter_by_asset_type(
        self,
        client: AsyncClient,
        db: AsyncSession,
        _patch_auth,
        test_tenant: Tenant,
    ):
        # Create a boat and a jetski.
        boat = Asset(
            name="Test Boat",
            asset_type=AssetType.BOAT,
            identifier="BOAT-FILTER",
            tenant_id=test_tenant.id,
        )
        jetski = Asset(
            name="Test Jetski",
            asset_type=AssetType.JETSKI,
            identifier="JET-FILTER",
            tenant_id=test_tenant.id,
        )
        db.add_all([boat, jetski])
        await db.flush()

        resp = await client.get(
            "/api/v1/assets?asset_type=boat",
            headers=_auth_headers(uuid.uuid4(), uuid.uuid4()),
        )
        assert resp.status_code == 200
        data = resp.json()
        types = {item["asset_type"] for item in data["items"]}
        assert types == {"boat"}


class TestGetAsset:
    """GET /api/v1/assets/{asset_id}"""

    async def test_get_existing(
        self, client: AsyncClient, _patch_auth, test_asset: Asset
    ):
        resp = await client.get(
            f"/api/v1/assets/{test_asset.id}",
            headers=_auth_headers(uuid.uuid4(), uuid.uuid4()),
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == str(test_asset.id)

    async def test_get_nonexistent(self, client: AsyncClient, _patch_auth):
        fake_id = uuid.uuid4()
        resp = await client.get(
            f"/api/v1/assets/{fake_id}",
            headers=_auth_headers(uuid.uuid4(), uuid.uuid4()),
        )
        assert resp.status_code == 404

    async def test_tenant_isolation(
        self,
        client: AsyncClient,
        db: AsyncSession,
        _patch_auth,
        test_asset: Asset,
    ):
        """An asset belonging to another tenant should not be visible."""
        # Create a second tenant and an asset under it.
        other_tenant = Tenant(
            id=uuid.uuid4(), name="Other Marina", slug="other-marina"
        )
        db.add(other_tenant)
        await db.flush()

        other_asset = Asset(
            id=uuid.uuid4(),
            name="Other Jetski",
            asset_type=AssetType.JETSKI,
            identifier="OTHER-001",
            tenant_id=other_tenant.id,
        )
        db.add(other_asset)
        await db.flush()

        # The test_user belongs to test_tenant -- should NOT see other_asset.
        resp = await client.get(
            f"/api/v1/assets/{other_asset.id}",
            headers=_auth_headers(uuid.uuid4(), uuid.uuid4()),
        )
        assert resp.status_code == 404


class TestUpdateAsset:
    """PUT /api/v1/assets/{asset_id}"""

    async def test_update_name(
        self, client: AsyncClient, _patch_auth, test_asset: Asset
    ):
        resp = await client.put(
            f"/api/v1/assets/{test_asset.id}",
            json={"name": "Renamed Jetski"},
            headers=_auth_headers(uuid.uuid4(), uuid.uuid4()),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed Jetski"

    async def test_update_nonexistent(self, client: AsyncClient, _patch_auth):
        resp = await client.put(
            f"/api/v1/assets/{uuid.uuid4()}",
            json={"name": "Ghost"},
            headers=_auth_headers(uuid.uuid4(), uuid.uuid4()),
        )
        assert resp.status_code == 404


class TestDeleteAsset:
    """DELETE /api/v1/assets/{asset_id}"""

    async def test_soft_delete(
        self, client: AsyncClient, _patch_auth, test_asset: Asset, db: AsyncSession
    ):
        resp = await client.delete(
            f"/api/v1/assets/{test_asset.id}",
            headers=_auth_headers(uuid.uuid4(), uuid.uuid4()),
        )
        assert resp.status_code == 204

        # Verify it is soft-deleted (should not appear in GET).
        resp2 = await client.get(
            f"/api/v1/assets/{test_asset.id}",
            headers=_auth_headers(uuid.uuid4(), uuid.uuid4()),
        )
        assert resp2.status_code == 404

    async def test_delete_nonexistent(self, client: AsyncClient, _patch_auth):
        resp = await client.delete(
            f"/api/v1/assets/{uuid.uuid4()}",
            headers=_auth_headers(uuid.uuid4(), uuid.uuid4()),
        )
        assert resp.status_code == 404
