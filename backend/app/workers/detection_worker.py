"""Background task runner for damage detection.

This module is designed to be called from a FastAPI ``BackgroundTasks``
handler or a dedicated task queue (e.g. Celery, arq).  It creates its
own database session because it runs outside the request lifecycle.

The worker:
  1. Opens its own async DB session.
  2. Delegates to ``damage_detection.detect_damage``.
  3. Commits on success or rolls back + updates status on failure.
  4. Logs all outcomes for observability.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from app.db.session import async_session_factory
from app.models.inspection import Inspection, InspectionStatus
from app.services import damage_detection

logger = logging.getLogger(__name__)


async def _run_detection(
    inspection_id: uuid.UUID,
    before_photo_ids: list[uuid.UUID],
    after_photo_ids: list[uuid.UUID],
) -> None:
    """Internal coroutine that manages the full lifecycle.

    Opens a fresh session, runs the detection pipeline, and handles
    commit / rollback.
    """
    async with async_session_factory() as session:
        try:
            findings = await damage_detection.detect_damage(
                inspection_id=inspection_id,
                before_photo_ids=before_photo_ids,
                after_photo_ids=after_photo_ids,
                db=session,
            )
            await session.commit()

            logger.info(
                "Detection worker completed successfully",
                extra={
                    "inspection_id": str(inspection_id),
                    "num_findings": len(findings),
                },
            )

        except Exception:
            await session.rollback()
            logger.error(
                "Detection worker failed",
                extra={"inspection_id": str(inspection_id)},
                exc_info=True,
            )

            # Best-effort: mark the inspection as failed by reverting to PENDING.
            # Use a fresh session so the rollback above does not interfere.
            try:
                async with async_session_factory() as err_session:
                    from sqlalchemy import select, update

                    stmt = (
                        update(Inspection)
                        .where(Inspection.id == inspection_id)
                        .values(status=InspectionStatus.PENDING)
                    )
                    await err_session.execute(stmt)
                    await err_session.commit()
                    logger.info(
                        "Inspection status reset to PENDING after failure",
                        extra={"inspection_id": str(inspection_id)},
                    )
            except Exception:
                logger.error(
                    "Failed to reset inspection status after detection failure",
                    extra={"inspection_id": str(inspection_id)},
                    exc_info=True,
                )


def run_detection_task(
    inspection_id: uuid.UUID,
    before_photo_ids: list[uuid.UUID],
    after_photo_ids: list[uuid.UUID],
) -> None:
    """Entry point for background detection.

    If there is already a running event loop (e.g. inside a FastAPI
    ``BackgroundTasks`` callback), schedule the coroutine on it.
    Otherwise, create a new loop.

    Usage from a FastAPI endpoint::

        from fastapi import BackgroundTasks

        @router.post("/detect")
        async def trigger_detection(
            ...,
            background_tasks: BackgroundTasks,
        ):
            background_tasks.add_task(
                run_detection_task,
                inspection_id,
                before_photo_ids,
                after_photo_ids,
            )
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    coro = _run_detection(inspection_id, before_photo_ids, after_photo_ids)

    if loop and loop.is_running():
        # We are inside an event loop (e.g. FastAPI BackgroundTasks).
        # Schedule the coroutine as a task.
        loop.create_task(coro)
    else:
        # No running loop -- create one (e.g. called from a plain thread).
        asyncio.run(coro)
