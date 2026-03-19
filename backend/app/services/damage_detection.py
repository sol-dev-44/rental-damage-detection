"""Core damage-detection orchestration service.

Coordinates the full pipeline:
  1. Fetch photo records from the database.
  2. Download image bytes from R2 storage.
  3. Validate image quality (blur, brightness, resolution).
  4. Retrieve few-shot examples via metadata-based filtering.
  5. Build the prompt using Jinja2 templates.
  6. Call Claude via the vision API wrapper.
  7. Parse the structured response.
  8. Create ``Finding`` records in the database.
  9. Look up repair costs from the ``RepairCostLookup`` table.
 10. Update inspection status through the workflow.

This is retrieval-augmented prompting -- Claude receives relevant past
corrections as in-context examples but has no persistent memory.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.ml import claude_client
from app.ml import few_shot_engine
from app.ml import metrics_tracker
from app.models.asset import Asset
from app.models.finding import DamageSeverity, Finding, FindingStatus
from app.models.inspection import Inspection, InspectionStatus
from app.models.photo import Photo
from app.services import image_validator
from app.services import prompt_builder
from app.services import repair_cost_service
from app.services import storage_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SEVERITY_MAP: dict[str, DamageSeverity] = {
    "minor": DamageSeverity.MINOR,
    "moderate": DamageSeverity.MODERATE,
    "major": DamageSeverity.MAJOR,
    "severe": DamageSeverity.SEVERE,
}


def _parse_severity(raw: str) -> DamageSeverity:
    """Map a raw severity string from Claude's response to the enum."""
    normalised = raw.strip().lower()
    severity = _SEVERITY_MAP.get(normalised)
    if severity is None:
        logger.warning("Unknown severity '%s' from Claude, defaulting to MINOR", raw)
        return DamageSeverity.MINOR
    return severity


async def _fetch_photos(
    photo_ids: list[uuid.UUID],
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> list[Photo]:
    """Load photo records from the database, scoped to tenant."""
    if not photo_ids:
        return []
    stmt = select(Photo).where(
        Photo.id.in_(photo_ids),
        Photo.tenant_id == tenant_id,
        Photo.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _download_and_validate_photos(
    photos: list[Photo],
) -> list[tuple[bytes, str, Photo]]:
    """Download each photo from R2 and run quality validation.

    Returns a list of (bytes, content_type, Photo) tuples for photos
    that pass validation.  Photos that fail are logged and skipped.
    """
    valid: list[tuple[bytes, str, Photo]] = []
    for photo in photos:
        try:
            img_bytes = await storage_service.download_photo(photo.r2_key)
        except Exception:
            logger.error(
                "Failed to download photo from R2",
                extra={"photo_id": str(photo.id), "r2_key": photo.r2_key},
                exc_info=True,
            )
            continue

        validation = image_validator.validate_image(img_bytes, photo.content_type)
        if not validation.is_valid:
            logger.warning(
                "Photo failed quality validation, skipping",
                extra={
                    "photo_id": str(photo.id),
                    "reasons": validation.reasons,
                    "quality_score": validation.quality_score,
                },
            )
            continue

        valid.append((img_bytes, photo.content_type, photo))

    return valid


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def detect_damage(
    *,
    inspection_id: uuid.UUID,
    before_photo_ids: list[uuid.UUID],
    after_photo_ids: list[uuid.UUID],
    db: AsyncSession,
) -> list[Finding]:
    """Run the full damage-detection pipeline for an inspection.

    Parameters
    ----------
    inspection_id:
        ID of the post-rental inspection to analyse.
    before_photo_ids:
        Photo IDs from the pre-rental inspection (baseline).
    after_photo_ids:
        Photo IDs from the post-rental inspection (to be analysed).
    db:
        Active async database session (caller manages the transaction).

    Returns
    -------
    list[Finding]
        The newly created ``Finding`` ORM objects (already flushed to
        the session but not yet committed).

    Raises
    ------
    ValueError
        If the inspection is not found or has no valid after photos.
    """
    settings = get_settings()
    t0 = time.monotonic()

    # -- 1. Load inspection and asset context ------------------------------
    insp_result = await db.execute(
        select(Inspection).where(Inspection.id == inspection_id)
    )
    inspection = insp_result.scalar_one_or_none()
    if inspection is None:
        raise ValueError(f"Inspection {inspection_id} not found")

    tenant_id = inspection.tenant_id

    asset_result = await db.execute(
        select(Asset).where(Asset.id == inspection.asset_id)
    )
    asset = asset_result.scalar_one_or_none()
    if asset is None:
        raise ValueError(f"Asset {inspection.asset_id} not found")

    # -- 2. Update status to ANALYZING -------------------------------------
    inspection.status = InspectionStatus.ANALYZING
    await db.flush()

    # -- 3. Fetch and validate photos --------------------------------------
    before_photos = await _fetch_photos(before_photo_ids, tenant_id, db)
    after_photos = await _fetch_photos(after_photo_ids, tenant_id, db)

    before_valid = await _download_and_validate_photos(before_photos)
    after_valid = await _download_and_validate_photos(after_photos)

    if not after_valid:
        raise ValueError(
            "No valid after-photos available after quality validation. "
            "Cannot proceed with damage detection."
        )

    # -- 4. Retrieve few-shot examples (metadata-based, not vector) --------
    asset_type_str = asset.asset_type.value
    few_shot_examples = await few_shot_engine.get_similar_cases(
        asset_type=asset_type_str,
        damage_types=None,  # No pre-filtering by damage type on first pass.
        tenant_id=tenant_id,
        limit=settings.SIMILAR_CASES_LIMIT,
        db=db,
    )

    # -- 5. Gather accuracy context for prompt calibration -----------------
    accuracy_by_type = await metrics_tracker.get_accuracy_by_asset_type(tenant_id, db)
    accuracy_context: dict[str, Any] | None = None
    if accuracy_by_type:
        accuracy_context = {
            f"{k} overall accuracy": f"{v['accuracy'] * 100:.0f}%"
            for k, v in accuracy_by_type.items()
        }

    # -- 6. Build prompt ---------------------------------------------------
    system_prompt = prompt_builder.build_damage_detection_prompt(
        asset_type=asset_type_str,
        asset_identifier=asset.identifier,
        asset_metadata=asset.metadata_,
        few_shot_examples=few_shot_examples if few_shot_examples else None,
        accuracy_context=accuracy_context,
    )

    user_text = prompt_builder.build_user_message(
        num_before=len(before_valid),
        num_after=len(after_valid),
    )

    # -- 7. Call Claude vision API -----------------------------------------
    before_images = [(b, ct) for b, ct, _ in before_valid]
    after_images = [(b, ct) for b, ct, _ in after_valid]

    claude_result = claude_client.send_vision_request(
        system_prompt=system_prompt,
        user_text=user_text,
        before_images=before_images if before_images else None,
        after_images=after_images,
    )

    if claude_result.error:
        logger.error(
            "Claude API call failed",
            extra={
                "inspection_id": str(inspection_id),
                "error": claude_result.error,
            },
        )
        raise RuntimeError(f"Claude API error: {claude_result.error}")

    # -- 8. Parse response and create findings -----------------------------
    parsed = claude_result.parsed_json
    if parsed is None:
        logger.error(
            "Failed to parse JSON from Claude response",
            extra={
                "inspection_id": str(inspection_id),
                "raw_text": claude_result.raw_text[:500],
            },
        )
        raise RuntimeError("Claude returned unparseable response")

    raw_findings = parsed.get("findings", [])
    min_confidence = settings.MIN_CONFIDENCE_THRESHOLD

    # Map after photos by index for bounding_box association.
    after_photo_map = {i: photo for i, (_, _, photo) in enumerate(after_valid)}
    # Use the first before photo for before_photo_id (if any).
    first_before_photo = before_valid[0][2] if before_valid else None

    created_findings: list[Finding] = []

    for idx, raw in enumerate(raw_findings):
        confidence = raw.get("confidence_score", 0)
        if confidence < min_confidence:
            logger.info(
                "Skipping low-confidence finding",
                extra={
                    "confidence": confidence,
                    "threshold": min_confidence,
                    "damage_type": raw.get("damage_type"),
                },
            )
            continue

        severity = _parse_severity(raw.get("severity", "minor"))

        # Associate with the first after photo (or a specific one if
        # we can identify it later from bounding box context).
        after_photo = after_photo_map.get(0)

        finding = Finding(
            inspection_id=inspection_id,
            tenant_id=tenant_id,
            damage_type=raw.get("damage_type", "unknown"),
            location_description=raw.get("location_description", ""),
            severity=severity,
            confidence_score=confidence,
            ai_reasoning=raw.get("ai_reasoning"),
            status=FindingStatus.PENDING,
            before_photo_id=first_before_photo.id if first_before_photo else None,
            after_photo_id=after_photo.id if after_photo else None,
            bounding_box=raw.get("bounding_box"),
        )
        db.add(finding)
        created_findings.append(finding)

    await db.flush()

    # -- 9. Look up repair costs for each finding --------------------------
    for finding in created_findings:
        cost_estimate = await repair_cost_service.get_estimated_cost(
            asset_type=asset_type_str,
            damage_type=finding.damage_type,
            severity=finding.severity.value,
            tenant_id=tenant_id,
            db=db,
        )
        if cost_estimate:
            logger.info(
                "Repair cost estimate found",
                extra={
                    "finding_id": str(finding.id),
                    "avg_cost": cost_estimate.avg_cost,
                    "currency": cost_estimate.currency,
                },
            )
        # Cost data is informational only at this stage; it will be
        # surfaced to the operator via the findings API response.

    # -- 10. Update inspection status to REVIEWED --------------------------
    inspection.status = InspectionStatus.REVIEWED
    await db.flush()

    duration = time.monotonic() - t0
    logger.info(
        "Damage detection completed",
        extra={
            "inspection_id": str(inspection_id),
            "num_findings": len(created_findings),
            "api_cost_usd": claude_result.estimated_cost_usd,
            "api_tokens_in": claude_result.input_tokens,
            "api_tokens_out": claude_result.output_tokens,
            "duration_s": round(duration, 2),
        },
    )

    return created_findings
