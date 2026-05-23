"""Eval route — assembles per-run metrics + live predictions + prev-run delta.

`GET /api/training/{run_id}/eval`

  * 404 if the TrainRun is unknown.
  * 422 if the run hasn't reached the `succeeded` terminal state — eval is
    only meaningful after metrics have been persisted by the M7 SSE relay.
  * 502 on any InspectServiceError when fetching live predictions.
  * 200 with `{run_id, metrics, predictions, prev_metrics}` otherwise.

The TrainingClient factory is shared with `routes.training` so tests
override both surfaces with a single `set_training_client_factory` call.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from indusia_visual_editor.config import get_config
from indusia_visual_editor.db.models import TrainRun
from indusia_visual_editor.db.session import get_session
from indusia_visual_editor.routes import training as _training_route_module
from indusia_visual_editor.services.inspect_service.exceptions import (
    InspectServiceConnectionError,
    InspectServiceError,
    InspectServiceResponseError,
    InspectServiceTimeoutError,
)
from indusia_visual_editor.utils.responses import success


router = APIRouter(prefix="/api/training", tags=["eval"])


@router.get("/{run_id}/eval")
async def get_eval(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    row = await session.get(TrainRun, run_id)
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"train_run {run_id} not found"
        )
    if row.status != "succeeded":
        raise HTTPException(
            status_code=422,
            detail=(
                f"train_run {run_id} is in status={row.status!r}; eval is only "
                f"available after the run reaches 'succeeded'"
            ),
        )

    # Previous succeeded run for the same project (most-recent excluding self).
    # `ended_at desc` because that's the lifecycle-truth ordering — `started_at`
    # would let a slow earlier run mask a faster recent one.
    prev_row = (
        await session.execute(
            select(TrainRun)
            .where(
                TrainRun.project_id == row.project_id,
                TrainRun.status == "succeeded",
                TrainRun.id != row.id,
            )
            .order_by(desc(TrainRun.ended_at))
            .limit(1)
        )
    ).scalar_one_or_none()

    cfg = get_config()
    client = _training_route_module._training_client_factory(
        base_url=cfg.inspect_service_url, timeout=cfg.inspect_service_timeout
    )
    try:
        try:
            predictions = await client.get_predictions(row.service_job_id)
        except (
            InspectServiceConnectionError,
            InspectServiceTimeoutError,
            InspectServiceResponseError,
        ) as exc:
            raise HTTPException(
                status_code=502, detail=f"auto-inspect-service unavailable: {exc}"
            )
        except InspectServiceError as exc:
            raise HTTPException(
                status_code=502, detail=f"auto-inspect-service error: {exc}"
            )
    finally:
        await client.aclose()

    return success(
        data={
            "run_id": str(row.id),
            "metrics": row.metrics_json or {},
            "predictions": predictions,
            "prev_metrics": prev_row.metrics_json if prev_row else None,
        }
    )
