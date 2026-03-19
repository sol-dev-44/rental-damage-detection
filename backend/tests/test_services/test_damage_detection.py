"""Tests for the damage detection orchestration service.

Covers:
  - Prompt building with asset metadata and few-shot examples.
  - Parsing Claude's structured JSON response.
  - Creating Finding records from the parsed response.
  - Handling low-confidence findings (below threshold).
  - Error handling when Claude returns unparseable output.
"""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.claude_client import ClaudeVisionResult
from app.models.asset import Asset, AssetType
from app.models.finding import DamageSeverity, Finding, FindingStatus
from app.models.inspection import Inspection, InspectionStatus
from app.models.photo import Photo
from app.models.tenant import Tenant
from app.models.user import User
from app.services import damage_detection, prompt_builder


# ---------------------------------------------------------------------------
# Prompt builder tests
# ---------------------------------------------------------------------------

class TestPromptBuilder:
    """Tests for ``prompt_builder.build_damage_detection_prompt``."""

    def test_basic_prompt_includes_asset_type(self):
        prompt = prompt_builder.build_damage_detection_prompt(
            asset_type="jetski",
            asset_identifier="HIN-123",
        )
        assert "jetski" in prompt
        assert "HIN-123" in prompt

    def test_prompt_includes_metadata(self):
        prompt = prompt_builder.build_damage_detection_prompt(
            asset_type="boat",
            asset_identifier="REG-456",
            asset_metadata={"year": 2022, "make": "Boston Whaler"},
        )
        assert "Boston Whaler" in prompt
        assert "2022" in prompt

    def test_prompt_includes_few_shot_examples(self):
        examples = [
            {
                "original_damage_type": "scratch",
                "original_severity": "major",
                "feedback_type": "false_positive",
                "corrected_damage_type": None,
                "corrected_severity": None,
                "operator_notes": "This was a reflection, not a scratch.",
            },
        ]
        prompt = prompt_builder.build_damage_detection_prompt(
            asset_type="jetski",
            asset_identifier="HIN-789",
            few_shot_examples=examples,
        )
        assert "reflection" in prompt
        assert "false_positive" in prompt
        assert "Example 1" in prompt

    def test_prompt_includes_accuracy_context(self):
        accuracy = {"jetski scratch accuracy": "62%"}
        prompt = prompt_builder.build_damage_detection_prompt(
            asset_type="jetski",
            asset_identifier="HIN-000",
            accuracy_context=accuracy,
        )
        assert "62%" in prompt
        assert "jetski scratch accuracy" in prompt

    def test_prompt_includes_false_positive_patterns(self):
        prompt = prompt_builder.build_damage_detection_prompt(
            asset_type="jetski",
            asset_identifier="HIN-111",
        )
        # Jetski false-positive patterns are defined in prompt_builder module.
        assert "Water spots" in prompt or "salt residue" in prompt

    def test_prompt_requests_json_output(self):
        prompt = prompt_builder.build_damage_detection_prompt(
            asset_type="other",
            asset_identifier="X-001",
        )
        assert "JSON" in prompt
        assert "findings" in prompt

    def test_user_message_with_before_photos(self):
        msg = prompt_builder.build_user_message(num_before=3, num_after=5)
        assert "3 BEFORE" in msg
        assert "5 AFTER" in msg

    def test_user_message_without_before_photos(self):
        msg = prompt_builder.build_user_message(num_before=0, num_after=2)
        assert "No before photos" in msg
        assert "2 AFTER" in msg


# ---------------------------------------------------------------------------
# Claude response parsing tests
# ---------------------------------------------------------------------------

class TestResponseParsing:
    """Tests for parsing Claude's structured JSON response and creating findings."""

    def test_parse_severity_valid(self):
        assert damage_detection._parse_severity("minor") == DamageSeverity.MINOR
        assert damage_detection._parse_severity("moderate") == DamageSeverity.MODERATE
        assert damage_detection._parse_severity("major") == DamageSeverity.MAJOR
        assert damage_detection._parse_severity("severe") == DamageSeverity.SEVERE

    def test_parse_severity_case_insensitive(self):
        assert damage_detection._parse_severity("MINOR") == DamageSeverity.MINOR
        assert damage_detection._parse_severity("  Major ") == DamageSeverity.MAJOR

    def test_parse_severity_unknown_defaults_to_minor(self):
        assert damage_detection._parse_severity("critical") == DamageSeverity.MINOR
        assert damage_detection._parse_severity("") == DamageSeverity.MINOR


class TestDetectDamage:
    """Integration-style tests for the ``detect_damage`` function.

    These mock external dependencies (R2, Claude) and exercise the
    orchestration logic with a real (in-memory SQLite) database.
    """

    async def test_creates_findings_from_claude_response(
        self,
        db: AsyncSession,
        test_tenant: Tenant,
        test_user: User,
        test_asset: Asset,
        test_inspection: Inspection,
        test_photo: Photo,
        mock_claude_client,
    ):
        """Verify that findings are created for valid Claude detections."""
        # Create a simple test image (1x1 white JPEG-like).
        from PIL import Image
        import io

        img = Image.new("RGB", (800, 600), color="white")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        fake_bytes = buf.getvalue()

        with patch(
            "app.services.storage_service.download_photo",
            new_callable=AsyncMock,
            return_value=fake_bytes,
        ):
            findings = await damage_detection.detect_damage(
                inspection_id=test_inspection.id,
                before_photo_ids=[],
                after_photo_ids=[test_photo.id],
                db=db,
            )

        # The mock_claude_response fixture has 2 findings, both above the
        # default confidence threshold of 70.
        assert len(findings) == 2
        assert findings[0].damage_type == "scratch"
        assert findings[0].severity == DamageSeverity.MODERATE
        assert findings[0].status == FindingStatus.PENDING
        assert findings[0].inspection_id == test_inspection.id
        assert findings[0].tenant_id == test_tenant.id

    async def test_skips_low_confidence_findings(
        self,
        db: AsyncSession,
        test_tenant: Tenant,
        test_user: User,
        test_asset: Asset,
        test_inspection: Inspection,
        test_photo: Photo,
    ):
        """Findings below MIN_CONFIDENCE_THRESHOLD should be skipped."""
        low_conf_response = {
            "findings": [
                {
                    "damage_type": "scratch",
                    "location_description": "Somewhere",
                    "severity": "minor",
                    "confidence_score": 40,  # Below threshold of 70.
                    "ai_reasoning": "Maybe a scratch?",
                    "bounding_box": None,
                },
            ],
        }

        mock_result = ClaudeVisionResult(
            parsed_json=low_conf_response,
            raw_text=json.dumps(low_conf_response),
            input_tokens=1000,
            output_tokens=200,
            estimated_cost_usd=0.006,
            model="claude-sonnet-4-20250514",
            duration_seconds=2.0,
        )

        from PIL import Image
        import io

        img = Image.new("RGB", (800, 600), color="white")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        fake_bytes = buf.getvalue()

        with (
            patch(
                "app.ml.claude_client.send_vision_request",
                return_value=mock_result,
            ),
            patch(
                "app.services.storage_service.download_photo",
                new_callable=AsyncMock,
                return_value=fake_bytes,
            ),
        ):
            findings = await damage_detection.detect_damage(
                inspection_id=test_inspection.id,
                before_photo_ids=[],
                after_photo_ids=[test_photo.id],
                db=db,
            )

        assert len(findings) == 0

    async def test_updates_inspection_status(
        self,
        db: AsyncSession,
        test_tenant: Tenant,
        test_user: User,
        test_asset: Asset,
        test_inspection: Inspection,
        test_photo: Photo,
        mock_claude_client,
    ):
        """Inspection should transition to REVIEWED on completion."""
        from PIL import Image
        import io

        img = Image.new("RGB", (800, 600), color="white")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        fake_bytes = buf.getvalue()

        with patch(
            "app.services.storage_service.download_photo",
            new_callable=AsyncMock,
            return_value=fake_bytes,
        ):
            await damage_detection.detect_damage(
                inspection_id=test_inspection.id,
                before_photo_ids=[],
                after_photo_ids=[test_photo.id],
                db=db,
            )

        await db.refresh(test_inspection)
        assert test_inspection.status == InspectionStatus.REVIEWED

    async def test_raises_on_claude_error(
        self,
        db: AsyncSession,
        test_tenant: Tenant,
        test_user: User,
        test_asset: Asset,
        test_inspection: Inspection,
        test_photo: Photo,
    ):
        """RuntimeError should be raised if Claude returns an error."""
        error_result = ClaudeVisionResult(
            error="Rate limit exceeded",
            model="claude-sonnet-4-20250514",
        )

        from PIL import Image
        import io

        img = Image.new("RGB", (800, 600), color="white")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        fake_bytes = buf.getvalue()

        with (
            patch(
                "app.ml.claude_client.send_vision_request",
                return_value=error_result,
            ),
            patch(
                "app.services.storage_service.download_photo",
                new_callable=AsyncMock,
                return_value=fake_bytes,
            ),
            pytest.raises(RuntimeError, match="Claude API error"),
        ):
            await damage_detection.detect_damage(
                inspection_id=test_inspection.id,
                before_photo_ids=[],
                after_photo_ids=[test_photo.id],
                db=db,
            )

    async def test_raises_on_no_valid_after_photos(
        self,
        db: AsyncSession,
        test_tenant: Tenant,
        test_user: User,
        test_asset: Asset,
        test_inspection: Inspection,
        test_photo: Photo,
    ):
        """ValueError should be raised if all after photos fail validation."""
        # Return tiny 1x1 image that will fail resolution check.
        from PIL import Image
        import io

        img = Image.new("RGB", (10, 10), color="white")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        tiny_bytes = buf.getvalue()

        with (
            patch(
                "app.services.storage_service.download_photo",
                new_callable=AsyncMock,
                return_value=tiny_bytes,
            ),
            pytest.raises(ValueError, match="No valid after-photos"),
        ):
            await damage_detection.detect_damage(
                inspection_id=test_inspection.id,
                before_photo_ids=[],
                after_photo_ids=[test_photo.id],
                db=db,
            )
