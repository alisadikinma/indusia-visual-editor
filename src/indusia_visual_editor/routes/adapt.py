"""Adapter route — POST writes graphflow tree, GET lists history.

POST /api/projects/{id}/adapt
  Body: AdaptRequest{lsf_annotation: LSAnnotation}
  → calls compose_from_project (Phase 4.5), persists an AdaptRun row,
    returns 201 envelope with the new row.
  → 422 envelope on NoPlanError or NoInspectedRegionsError (typed
    exceptions from compose).
  → 502 envelope on filesystem OSError (no row persisted).

GET /api/projects/{id}/adapt
  → 200 envelope, list of latest 20 AdaptRun rows by created_at desc.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from indusia_visual_editor.config import get_config
from indusia_visual_editor.db.models import AdaptRun
from indusia_visual_editor.db.session import get_session
from indusia_visual_editor.schemas.adapt import AdaptRequest, AdaptRunRead
from indusia_visual_editor.services.adapter.compose import (
    NoInspectedRegionsError,
    NoPlanError,
    compose_from_project,
)
from indusia_visual_editor.services.auth.dependencies import get_current_user
from indusia_visual_editor.services.project.crud import get_project
from indusia_visual_editor.utils.responses import success

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_id}/adapt", tags=["adapter"])


def _serialize(row: AdaptRun) -> dict:
    return AdaptRunRead.model_validate(row).model_dump(mode="json")


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_user)],
)
async def create_adapt_run(
    project_id: uuid.UUID,
    payload: AdaptRequest,
    session: AsyncSession = Depends(get_session),
):
    await get_project(session, project_id)  # 404 if missing

    cfg = get_config()
    models_root = Path(cfg.models_root).resolve()

    try:
        result = await compose_from_project(
            session=session,
            project_id=project_id,
            lsf_annotation=payload.lsf_annotation,
            models_root=models_root,
        )
    except NoPlanError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except NoInspectedRegionsError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except OSError as exc:
        logger.exception("adapter write failed", extra={"project_id": project_id})
        raise HTTPException(
            status_code=502, detail=f"filesystem write failed: {exc}"
        )

    row = AdaptRun(
        project_id=project_id,
        pcb_name=result.pcb_name,
        model_dir=str(result.model_dir),
        inspected_count=result.inspected_count,
        status="ok",
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)

    return success(
        data=_serialize(row),
        message="model dir written",
        status_code=status.HTTP_201_CREATED,
    )


@router.get("")
async def list_adapt_runs(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    await get_project(session, project_id)
    rows = (
        await session.execute(
            select(AdaptRun)
            .where(AdaptRun.project_id == project_id)
            .order_by(desc(AdaptRun.created_at))
            .limit(20)
        )
    ).scalars().all()
    return success(data=[_serialize(r) for r in rows])
