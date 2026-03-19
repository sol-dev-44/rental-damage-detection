"""Repair cost lookup service.

Returns estimated repair costs from the ``repair_cost_lookups`` table
based on asset type, damage type, and severity.  Costs are operator-
managed data -- they are NOT AI-generated.

If no matching row exists, ``None`` is returned so the caller can
surface "no estimate available" rather than fabricating a number.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.repair_cost import RepairCostLookup

logger = logging.getLogger(__name__)


@dataclass
class RepairCostEstimate:
    """Structured cost estimate returned by the lookup."""

    min_cost: float
    max_cost: float
    avg_cost: float
    currency: str


async def get_estimated_cost(
    *,
    asset_type: str,
    damage_type: str,
    severity: str,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> RepairCostEstimate | None:
    """Look up estimated repair cost from the ``RepairCostLookup`` table.

    Parameters
    ----------
    asset_type:
        One of the ``AssetType`` enum values (e.g. ``"jetski"``).
    damage_type:
        Damage category string (e.g. ``"scratch"``, ``"dent"``).
    severity:
        One of the ``DamageSeverity`` enum values (e.g. ``"minor"``).
    tenant_id:
        Tenant scope -- costs are tenant-specific.
    db:
        Active async database session.

    Returns
    -------
    RepairCostEstimate | None
        The matched cost range, or ``None`` if no data exists for this
        combination.
    """
    stmt = select(RepairCostLookup).where(
        RepairCostLookup.tenant_id == tenant_id,
        RepairCostLookup.asset_type == asset_type,
        RepairCostLookup.damage_type == damage_type,
        RepairCostLookup.severity == severity,
        RepairCostLookup.deleted_at.is_(None),
    )

    result = await db.execute(stmt)
    row = result.scalar_one_or_none()

    if row is None:
        logger.debug(
            "No repair cost data found",
            extra={
                "asset_type": asset_type,
                "damage_type": damage_type,
                "severity": severity,
                "tenant_id": str(tenant_id),
            },
        )
        return None

    return RepairCostEstimate(
        min_cost=row.min_cost,
        max_cost=row.max_cost,
        avg_cost=row.avg_cost,
        currency=row.currency,
    )
