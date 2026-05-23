"""Training routes — bridge to auto-inspect-service (Phase 7.3+).

POST /api/projects/{project_id}/training/start
  Reads latest AdaptRun.model_dir for the project, calls
  `auto-inspect-service /api/training/start`, persists a TrainRun row in
  status='pending' with the service-assigned job_id, returns the row.

  422 if the project has no AdaptRun yet (operator must approve the
  adapter pipeline before training).
  502 on any InspectServiceError — no row is leaked.

GET /api/projects/{project_id}/training
  Returns history of TrainRuns for the project, newest first.

Phase 7.4 layers `/api/training/{run_id}/stream` on top of this; the SSE
relay is the thing the operator-facing UI subscribes to once start has
returned a row.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from indusia_visual_editor.config import get_config
from indusia_visual_editor.db.models import AdaptRun, TrainRun
from indusia_visual_editor.db.session import get_session
from indusia_visual_editor.schemas.training import TrainRunRead
from indusia_visual_editor.services.inspect_service.exceptions import (
    InspectServiceConnectionError,
    InspectServiceError,
    InspectServiceResponseError,
    InspectServiceTimeoutError,
)
from indusia_visual_editor.services.inspect_service.training_client import (
    TrainingClient,
)
from indusia_visual_editor.services.project.crud import get_project
from indusia_visual_editor.utils.responses import success


router = APIRouter(prefix="/api/projects/{project_id}/training", tags=["training"])

# Test seam — assigned to TrainingClient in production. Tests override
# via `set_training_client_factory(_FakeTrainingClient)` (mirrors the
# `set_llm_client_factory` pattern from Phase 3.4).
_training_client_factory = TrainingClient


def set_training_client_factory(factory) -> None:
    """Test-only seam to inject a fake TrainingClient."""
    global _training_client_factory
    _training_client_factory = factory


def reset_training_client_factory() -> None:
    global _training_client_factory
    _training_client_factory = TrainingClient


def _serialize(row: TrainRun) -> dict:
    return TrainRunRead.model_validate(row).model_dump(mode="json")


@router.post("/start", status_code=status.HTTP_201_CREATED)
async def start_training(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    # 404 if project missing (raises ProjectNotFoundError → main.py handler).
    await get_project(session, project_id)

    # Latest AdaptRun wins — the most recently adapted graphflow tree is
    # what the operator currently sees in the canvas, so it's what we train.
    latest_adapt = (
        await session.execute(
            select(AdaptRun)
            .where(AdaptRun.project_id == project_id)
            .order_by(desc(AdaptRun.created_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest_adapt is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "project has no adapt_run yet; approve the pipeline via "
                "POST /api/projects/{id}/adapt before starting training"
            ),
        )

    cfg = get_config()
    client = _training_client_factory(
        base_url=cfg.inspect_service_url, timeout=cfg.inspect_service_timeout
    )
    try:
        try:
            job_id = await client.start_training(model_dir=latest_adapt.model_dir)
        except (
            InspectServiceConnectionError,
            InspectServiceTimeoutError,
            InspectServiceResponseError,
        ) as exc:
            raise HTTPException(
                status_code=502, detail=f"auto-inspect-service unavailable: {exc}"
            )
        except InspectServiceError as exc:
            # Defensive: future subclasses still funnel to 502.
            raise HTTPException(
                status_code=502, detail=f"auto-inspect-service error: {exc}"
            )
    finally:
        await client.aclose()

    row = TrainRun(
        project_id=project_id,
        adapt_run_id=latest_adapt.id,
        service_job_id=job_id,
        status="pending",
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)

    return success(
        data=_serialize(row),
        message="training started",
        status_code=status.HTTP_201_CREATED,
    )


@router.get("")
async def list_training_runs(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    await get_project(session, project_id)
    rows = (
        await session.execute(
            select(TrainRun)
            .where(TrainRun.project_id == project_id)
            .order_by(desc(TrainRun.started_at))
        )
    ).scalars().all()
    return success(data=[_serialize(r) for r in rows])
