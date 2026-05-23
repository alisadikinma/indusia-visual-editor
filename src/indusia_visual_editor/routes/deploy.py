"""Deploy route — Gate 2 promote-to-production (Phase 10.3).

POST /api/projects/{project_id}/deploy
  Looks up the latest succeeded TrainRun for the project, invokes the
  `ais model add → commit → push` subprocess sequence in the configured
  registry working directory, and persists a Deployment row with the
  outcome. The audit trail is ALWAYS persisted — successful or failed.

  201 on push success, 422 if no succeeded TrainRun, 502 on push failure
  (deployment row still persists with status='failed' for audit).

GET /api/projects/{project_id}/deploy
  Returns deployment history for the project, newest first.

The actual `push_model` callable is overridable via
`set_push_model_callable` so tests inject a fake (no real `ais`
subprocess in CI).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from indusia_visual_editor.config import get_config
from indusia_visual_editor.db.models import Deployment, TrainRun
from indusia_visual_editor.db.session import get_session
from indusia_visual_editor.schemas.deploy import DeploymentRead
from indusia_visual_editor.services.deploy.registry import (
    PushResult,
    push_model as _real_push_model,
)
from indusia_visual_editor.services.project.crud import get_project
from indusia_visual_editor.utils.responses import success


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/projects/{project_id}/deploy", tags=["deploy"])


# Test seam — assigned to the real subprocess wrapper in production.
# Tests override via `set_push_model_callable(_FakePush)` so no real
# `ais` binary is needed.
PushCallable = Callable[..., Awaitable[PushResult]]
_push_model_callable: PushCallable = _real_push_model


def set_push_model_callable(fn: PushCallable) -> None:
    global _push_model_callable
    _push_model_callable = fn


def reset_push_model_callable() -> None:
    global _push_model_callable
    _push_model_callable = _real_push_model


def _serialize(row: Deployment) -> dict[str, Any]:
    return DeploymentRead.model_validate(row).model_dump(mode="json")


def _build_model_version(run: TrainRun) -> str:
    """Human-readable version label for the registry commit.

    Uses `ended_at` (UTC, second precision) + a 6-char run-id suffix so
    two runs that finish in the same second still get unique labels. The
    registry itself is authoritative on identity (git SHA); this label is
    for the operator-facing UI.
    """
    ts = (run.ended_at or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
    return f"{ts}-{str(run.id)[:6]}"


@router.post("", status_code=status.HTTP_201_CREATED)
async def promote_to_production(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    project = await get_project(session, project_id)

    latest_succeeded = (
        await session.execute(
            select(TrainRun)
            .where(
                TrainRun.project_id == project_id,
                TrainRun.status == "succeeded",
            )
            .order_by(desc(TrainRun.ended_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest_succeeded is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "project has no succeeded train_run yet; finish training "
                "before promoting"
            ),
        )

    model_version = _build_model_version(latest_succeeded)
    cfg = get_config()
    result = await _push_model_callable(
        pcb_name=project.slug,
        commit_message=f"promote {project.slug} {model_version}",
        registry_root=Path(cfg.registry_root),
        ais_binary=cfg.ais_binary,
        timeout=cfg.ais_push_timeout_secs,
    )

    error_text: str | None
    if result.ok:
        row_status = "succeeded"
        error_text = None
    else:
        row_status = "failed"
        error_text = (
            f"stage={result.stage} rc={result.returncode}: "
            f"{result.stderr.strip() or result.stdout.strip() or 'no output'}"
        )

    row = Deployment(
        project_id=project_id,
        train_run_id=latest_succeeded.id,
        model_version=model_version,
        status=row_status,
        error_text=error_text,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)

    if not result.ok:
        # Persist the row, then surface a 502 envelope — the audit trail
        # is locked in, the operator sees the failure.
        await session.commit()
        logger.warning(
            "deployment %s for project %s failed at stage=%s rc=%s",
            row.id,
            project_id,
            result.stage,
            result.returncode,
        )
        raise HTTPException(
            status_code=502,
            detail=(
                f"ais model {result.stage} failed: "
                f"{result.stderr.strip() or 'unknown error'}"
            ),
        )

    return success(
        data=_serialize(row),
        message="model promoted",
        status_code=status.HTTP_201_CREATED,
    )


@router.get("")
async def list_deployments(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    await get_project(session, project_id)
    rows = (
        await session.execute(
            select(Deployment)
            .where(Deployment.project_id == project_id)
            .order_by(desc(Deployment.deployed_at))
        )
    ).scalars().all()
    return success(data=[_serialize(r) for r in rows])
