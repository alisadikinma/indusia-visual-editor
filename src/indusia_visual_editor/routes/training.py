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

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from indusia_visual_editor.config import get_config
from indusia_visual_editor.db.models import AdaptRun, TrainRun
from indusia_visual_editor.db.session import get_session, get_sessionmaker
from indusia_visual_editor.routes import llm as _llm_route_module
from indusia_visual_editor.routes.dataset_stats import compute_dataset_stats
from indusia_visual_editor.schemas.training import TrainRunRead
from indusia_visual_editor.services.auth.dependencies import get_current_user
from indusia_visual_editor.services.inspect_service.exceptions import (
    InspectServiceConnectionError,
    InspectServiceError,
    InspectServiceResponseError,
    InspectServiceTimeoutError,
)
from indusia_visual_editor.services.inspect_service.training_client import (
    TrainingClient,
)
from indusia_visual_editor.services.llm.exceptions import (
    LlmConnectionError,
    LlmResponseError,
    LlmTimeoutError,
    LlmValidationError,
)
from indusia_visual_editor.services.llm.hyperparams import suggest_hyperparams
from indusia_visual_editor.services.project.crud import get_project
from indusia_visual_editor.utils.responses import success


logger = logging.getLogger(__name__)


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


@router.post(
    "/start",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_user)],
)
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


@router.post("/suggest-hyperparams", dependencies=[Depends(get_current_user)])
async def suggest_training_hyperparams(
    project_id: uuid.UUID,
    side: str,
    session: AsyncSession = Depends(get_session),
):
    """Compose dataset stats + a Gemma 4 hyperparam suggestion in one call.

    Used by the Gate-1 panel (M8.3) to render both the stats grid AND the
    suggested epochs/batch_size/aug-intensity without forcing the frontend
    to round-trip twice. The LLM client factory used here is the same
    `routes.llm._llm_client_factory` test seam already shipped in M3 —
    tests override it via `set_llm_client_factory`.
    """
    if side not in ("top", "bottom"):
        raise HTTPException(
            status_code=422, detail=f"side must be 'top' or 'bottom', got {side!r}"
        )

    await get_project(session, project_id)

    stats = await compute_dataset_stats(session, project_id, side)
    if stats is None:
        raise HTTPException(
            status_code=404,
            detail=f"no label yet for side={side}; finish the canvas pass first",
        )

    cfg = get_config()
    client = _llm_route_module._llm_client_factory(
        base_url=cfg.ollama_url, timeout=cfg.ollama_timeout
    )
    try:
        try:
            hp = await suggest_hyperparams(
                client=client,
                model=cfg.ollama_model_planner,
                dataset_stats=stats,
            )
        except (LlmConnectionError, LlmTimeoutError, LlmResponseError) as exc:
            raise HTTPException(
                status_code=502, detail=f"Ollama unavailable: {exc}"
            )
        except LlmValidationError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Ollama returned invalid hyperparameters: {exc}",
            )
    finally:
        await client.aclose()

    return success(
        data={
            "project_id": str(project_id),
            "side": side,
            "stats": stats,
            "hyperparameters": hp.model_dump(),
        }
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


# ---------------- Phase 7.4 — SSE relay ----------------
#
# The stream endpoint sits at `/api/training/{run_id}/stream` (not nested
# under `/projects/{id}`) so the frontend can re-attach by run_id alone,
# which is the identifier the start endpoint returns. A separate router
# is used because the prefix differs from the project-scoped router above.

stream_router = APIRouter(prefix="/api/training", tags=["training"])

# Event-name → terminal? map. The service contract — verified against
# auto-inspect-service during the M0 Phase 0.2 spike — is that `succeeded`,
# `failed`, and `cancelled` are terminal; `running` and `epoch` are
# intermediate. Any other event name passes through to the client without
# a row write (forward-compatible for future event kinds).
_TERMINAL_EVENTS = {"succeeded", "failed", "cancelled"}


async def _apply_event_to_row(run_id: uuid.UUID, event: dict) -> None:
    """Persist a single SSE event against the TrainRun row.

    Each event opens its own short-lived session — the EventSourceResponse
    generator outlives the request-scoped session, and holding a single
    session open for hours would tie up a pool connection.
    """

    kind = event.get("event")
    factory = get_sessionmaker()
    async with factory() as s:
        row = await s.get(TrainRun, run_id)
        if row is None:
            return
        if kind == "running" and row.status == "pending":
            row.status = "running"
        elif kind == "succeeded":
            row.status = "succeeded"
            row.metrics_json = event.get("metrics")
            row.ended_at = datetime.now(timezone.utc)
        elif kind == "failed":
            row.status = "failed"
            row.error_text = event.get("error") or "training failed"
            row.ended_at = datetime.now(timezone.utc)
        elif kind == "cancelled":
            row.status = "cancelled"
            row.ended_at = datetime.now(timezone.utc)
        await s.commit()


async def _mark_relay_failure(run_id: uuid.UUID, exc: Exception) -> None:
    """Mark the row failed when the relay itself cannot proceed (the
    auto-inspect-service stream errored before any terminal event)."""
    factory = get_sessionmaker()
    async with factory() as s:
        row = await s.get(TrainRun, run_id)
        if row is None:
            return
        row.status = "failed"
        row.error_text = f"stream relay error: {exc}"
        row.ended_at = datetime.now(timezone.utc)
        await s.commit()


@stream_router.get("/{run_id}/stream")
async def stream_training_progress(run_id: uuid.UUID):
    """Relay the auto-inspect-service SSE progress events to our caller.

    Returns 404 if the run isn't known. Otherwise opens the upstream stream,
    forwards each `data:` event verbatim, and updates the TrainRun row in
    place as the lifecycle advances. Service-side transport errors mark the
    row `failed` with `error_text` populated, then surface a final `error`
    event on the wire so the operator-facing UI can render the failure.
    """

    factory = get_sessionmaker()
    async with factory() as s:
        row = await s.get(TrainRun, run_id)
        if row is None:
            raise HTTPException(
                status_code=404, detail=f"train_run {run_id} not found"
            )
        service_job_id = row.service_job_id

    cfg = get_config()

    async def event_generator():
        client = _training_client_factory(
            base_url=cfg.inspect_service_url,
            timeout=cfg.inspect_service_timeout,
        )
        try:
            try:
                async for event in client.stream_progress(service_job_id):
                    await _apply_event_to_row(run_id, event)
                    yield {"data": json.dumps(event)}
                    if event.get("event") in _TERMINAL_EVENTS:
                        # Terminal — drain remaining iterator and stop.
                        break
            except InspectServiceError as exc:
                logger.warning(
                    "training stream relay error for run %s: %s", run_id, exc
                )
                await _mark_relay_failure(run_id, exc)
                yield {"data": json.dumps({"event": "error", "error": str(exc)})}
        finally:
            await client.aclose()

    return EventSourceResponse(event_generator())
