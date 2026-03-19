"""Tests for the few-shot example retrieval engine.

Covers:
  - Metadata-based filtering by asset type.
  - Filtering by damage type when provided.
  - Example formatting for the prompt builder.
  - Empty results when no matching corrections exist.
  - Tenant isolation.
  - Ordering by recency (most recent corrections first).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.few_shot_engine import get_similar_cases
from app.models.asset import Asset, AssetType
from app.models.feedback import Feedback, FeedbackType
from app.models.finding import DamageSeverity, Finding, FindingStatus
from app.models.inspection import Inspection, InspectionStatus, InspectionType
from app.models.photo import Photo
from app.models.tenant import Tenant
from app.models.user import User, UserRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_correction(
    db: AsyncSession,
    *,
    tenant: Tenant,
    user: User,
    asset: Asset,
    damage_type: str = "scratch",
    severity: DamageSeverity = DamageSeverity.MODERATE,
    feedback_type: FeedbackType = FeedbackType.FALSE_POSITIVE,
    corrected_damage_type: str | None = None,
    corrected_severity: str | None = None,
    operator_notes: str | None = None,
) -> Feedback:
    """Create a full chain: inspection -> photo -> finding -> feedback."""
    inspection = Inspection(
        id=uuid.uuid4(),
        asset_id=asset.id,
        inspection_type=InspectionType.POST_RENTAL,
        inspector_id=user.id,
        status=InspectionStatus.REVIEWED,
        tenant_id=tenant.id,
    )
    db.add(inspection)
    await db.flush()

    finding = Finding(
        id=uuid.uuid4(),
        inspection_id=inspection.id,
        damage_type=damage_type,
        location_description="Test location",
        severity=severity,
        confidence_score=80.0,
        status=FindingStatus.REJECTED if feedback_type == FeedbackType.FALSE_POSITIVE else FindingStatus.CONFIRMED,
        tenant_id=tenant.id,
    )
    db.add(finding)
    await db.flush()

    feedback = Feedback(
        id=uuid.uuid4(),
        finding_id=finding.id,
        inspection_id=inspection.id,
        feedback_type=feedback_type,
        operator_id=user.id,
        operator_notes=operator_notes,
        corrected_damage_type=corrected_damage_type,
        corrected_severity=corrected_severity,
        tenant_id=tenant.id,
    )
    db.add(feedback)
    await db.flush()

    return feedback


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGetSimilarCases:
    """Tests for ``get_similar_cases``."""

    async def test_returns_empty_when_no_feedback(
        self,
        db: AsyncSession,
        test_tenant: Tenant,
    ):
        """No corrections exist -- should return an empty list."""
        examples = await get_similar_cases(
            asset_type="jetski",
            tenant_id=test_tenant.id,
            db=db,
        )
        assert examples == []

    async def test_returns_corrections_for_matching_asset_type(
        self,
        db: AsyncSession,
        test_tenant: Tenant,
        test_user: User,
        test_asset: Asset,
    ):
        """Corrections on matching asset type should be returned."""
        await _create_correction(
            db,
            tenant=test_tenant,
            user=test_user,
            asset=test_asset,  # AssetType.JETSKI
            damage_type="scratch",
            feedback_type=FeedbackType.FALSE_POSITIVE,
            operator_notes="This was a water spot, not a scratch.",
        )

        examples = await get_similar_cases(
            asset_type="jetski",
            tenant_id=test_tenant.id,
            db=db,
        )
        assert len(examples) == 1
        assert examples[0]["original_damage_type"] == "scratch"
        assert examples[0]["feedback_type"] == "false_positive"
        assert examples[0]["operator_notes"] == "This was a water spot, not a scratch."

    async def test_does_not_return_true_positive_feedback(
        self,
        db: AsyncSession,
        test_tenant: Tenant,
        test_user: User,
        test_asset: Asset,
    ):
        """TRUE_POSITIVE feedback is confirmation, not a correction.
        The engine should only return actionable corrections."""
        await _create_correction(
            db,
            tenant=test_tenant,
            user=test_user,
            asset=test_asset,
            damage_type="dent",
            feedback_type=FeedbackType.TRUE_POSITIVE,
        )

        examples = await get_similar_cases(
            asset_type="jetski",
            tenant_id=test_tenant.id,
            db=db,
        )
        assert len(examples) == 0

    async def test_filters_by_damage_type_with_priority(
        self,
        db: AsyncSession,
        test_tenant: Tenant,
        test_user: User,
        test_asset: Asset,
    ):
        """When damage_types are specified, matching rows come first."""
        await _create_correction(
            db,
            tenant=test_tenant,
            user=test_user,
            asset=test_asset,
            damage_type="scratch",
            feedback_type=FeedbackType.FALSE_POSITIVE,
            operator_notes="Scratch false positive",
        )
        await _create_correction(
            db,
            tenant=test_tenant,
            user=test_user,
            asset=test_asset,
            damage_type="dent",
            feedback_type=FeedbackType.SEVERITY_ADJUSTED,
            corrected_severity="minor",
            operator_notes="Dent severity adjusted",
        )

        examples = await get_similar_cases(
            asset_type="jetski",
            damage_types=["scratch"],
            tenant_id=test_tenant.id,
            db=db,
        )

        assert len(examples) == 2
        # Scratch should come first (priority match).
        assert examples[0]["original_damage_type"] == "scratch"

    async def test_respects_limit(
        self,
        db: AsyncSession,
        test_tenant: Tenant,
        test_user: User,
        test_asset: Asset,
    ):
        """Only up to *limit* examples should be returned."""
        for i in range(10):
            await _create_correction(
                db,
                tenant=test_tenant,
                user=test_user,
                asset=test_asset,
                damage_type=f"damage_{i}",
                feedback_type=FeedbackType.FALSE_POSITIVE,
            )

        examples = await get_similar_cases(
            asset_type="jetski",
            tenant_id=test_tenant.id,
            limit=3,
            db=db,
        )
        assert len(examples) == 3

    async def test_tenant_isolation(
        self,
        db: AsyncSession,
        test_tenant: Tenant,
        test_user: User,
        test_asset: Asset,
    ):
        """Corrections from other tenants should not be returned."""
        # Create a correction under the test tenant.
        await _create_correction(
            db,
            tenant=test_tenant,
            user=test_user,
            asset=test_asset,
            damage_type="scratch",
            feedback_type=FeedbackType.FALSE_POSITIVE,
        )

        # Query with a different tenant_id.
        other_tenant_id = uuid.uuid4()
        examples = await get_similar_cases(
            asset_type="jetski",
            tenant_id=other_tenant_id,
            db=db,
        )
        assert len(examples) == 0

    async def test_does_not_return_different_asset_type(
        self,
        db: AsyncSession,
        test_tenant: Tenant,
        test_user: User,
    ):
        """Corrections on a different asset type should not appear."""
        boat = Asset(
            id=uuid.uuid4(),
            name="Test Boat",
            asset_type=AssetType.BOAT,
            identifier="BOAT-TEST",
            tenant_id=test_tenant.id,
        )
        db.add(boat)
        await db.flush()

        await _create_correction(
            db,
            tenant=test_tenant,
            user=test_user,
            asset=boat,
            damage_type="scratch",
            feedback_type=FeedbackType.FALSE_POSITIVE,
        )

        # Query for jetski -- should not see the boat correction.
        examples = await get_similar_cases(
            asset_type="jetski",
            tenant_id=test_tenant.id,
            db=db,
        )
        assert len(examples) == 0

    async def test_example_format_has_expected_keys(
        self,
        db: AsyncSession,
        test_tenant: Tenant,
        test_user: User,
        test_asset: Asset,
    ):
        """Each returned example should have the keys the prompt builder expects."""
        await _create_correction(
            db,
            tenant=test_tenant,
            user=test_user,
            asset=test_asset,
            damage_type="crack",
            feedback_type=FeedbackType.SEVERITY_ADJUSTED,
            corrected_severity="minor",
            operator_notes="Hairline crack, not major.",
        )

        examples = await get_similar_cases(
            asset_type="jetski",
            tenant_id=test_tenant.id,
            db=db,
        )
        assert len(examples) == 1
        ex = examples[0]
        assert "original_damage_type" in ex
        assert "original_severity" in ex
        assert "feedback_type" in ex
        assert "corrected_damage_type" in ex
        assert "corrected_severity" in ex
        assert "operator_notes" in ex
        assert ex["original_damage_type"] == "crack"
        assert ex["corrected_severity"] == "minor"
