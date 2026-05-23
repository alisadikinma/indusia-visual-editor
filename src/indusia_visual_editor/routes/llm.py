"""LLM planner route.

POST /api/projects/{project_id}/llm/plan
  Reads bom_items + golden_top asset, asks Ollama for a ProposedPipeline,
  persists a new versioned row to `proposed_pipelines`, returns the plan.

  422 if the project has no bom_items or no golden_top asset (we won't
  call the LLM without input — fast-fail on the route).
  502 if Ollama is unreachable or returns garbage.

GET /api/projects/{project_id}/llm/plan
  Returns the latest persisted ProposedPipeline (or 404 if none yet).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from indusia_visual_editor.config import get_config
from indusia_visual_editor.db.models import (
    Asset,
    AssetKind,
    BomItem,
    PreLabel,
    ProposedPipelineRow,
)
from indusia_visual_editor.db.session import get_session
from indusia_visual_editor.schemas.llm import ProposedPipelineRead
from indusia_visual_editor.schemas.prelabel import PreLabelRunRead
from indusia_visual_editor.services.asset.image_store import absolute_path
from indusia_visual_editor.services.auth.dependencies import get_current_user
from indusia_visual_editor.services.llm.client import OllamaClient
from indusia_visual_editor.services.llm.exceptions import (
    LlmConnectionError,
    LlmResponseError,
    LlmTimeoutError,
    LlmValidationError,
)
from indusia_visual_editor.services.llm.planner import (
    BomItemForPlanner,
    propose_pipeline,
)
from indusia_visual_editor.services.llm.prelabel import prelabel_designators
from indusia_visual_editor.services.project.crud import get_project
from indusia_visual_editor.utils.responses import success


router = APIRouter(prefix="/api/projects/{project_id}/llm", tags=["llm"])

# Test seam — assigned to OllamaClient in production. Tests override
# this with a fake client by monkeypatching the module attribute.
_llm_client_factory = OllamaClient


def set_llm_client_factory(factory) -> None:
    """Test-only seam to inject a fake OllamaClient."""
    global _llm_client_factory
    _llm_client_factory = factory


def reset_llm_client_factory() -> None:
    global _llm_client_factory
    _llm_client_factory = OllamaClient


async def _load_bom(session: AsyncSession, project_id: uuid.UUID) -> list[BomItem]:
    rows = (
        await session.execute(
            select(BomItem)
            .where(BomItem.project_id == project_id)
            .order_by(BomItem.designator)
        )
    ).scalars().all()
    return list(rows)


async def _load_golden_top(session: AsyncSession, project_id: uuid.UUID) -> Asset | None:
    row = (
        await session.execute(
            select(Asset)
            .where(
                Asset.project_id == project_id,
                Asset.kind == AssetKind.GOLDEN_TOP,
            )
            .order_by(desc(Asset.uploaded_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    return row


def _to_planner_items(rows: list[BomItem]) -> list[BomItemForPlanner]:
    return [
        BomItemForPlanner(
            designator=r.designator,
            value=r.value,
            package=r.package,
            component_type=r.component_type,
            mi_likely=r.mi_likely,
            qty=r.qty,
        )
        for r in rows
    ]


def _serialize(row: ProposedPipelineRow) -> dict:
    return {
        "id": str(row.id),
        "project_id": str(row.project_id),
        "version": row.version,
        "plan": row.dag_json,
        "created_at": row.created_at.isoformat(),
    }


@router.post(
    "/plan",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_user)],
)
async def create_plan(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    await get_project(session, project_id)  # 404 if missing

    bom_rows = await _load_bom(session, project_id)
    if not bom_rows:
        raise HTTPException(
            status_code=422, detail="project has no bom_items; upload a BOM first"
        )

    golden = await _load_golden_top(session, project_id)
    if golden is None:
        raise HTTPException(
            status_code=422,
            detail="project has no golden_top asset; upload one before planning",
        )

    golden_bytes = absolute_path(golden).read_bytes()

    cfg = get_config()
    client = _llm_client_factory(base_url=cfg.ollama_url, timeout=cfg.ollama_timeout)
    try:
        try:
            plan = await propose_pipeline(
                client=client,
                model=cfg.ollama_model_planner,
                bom_items=_to_planner_items(bom_rows),
                golden_image=golden_bytes,
            )
        except (LlmConnectionError, LlmTimeoutError, LlmResponseError) as exc:
            raise HTTPException(status_code=502, detail=f"Ollama unavailable: {exc}")
        except LlmValidationError as exc:
            raise HTTPException(
                status_code=502, detail=f"Ollama returned invalid plan: {exc}"
            )
    finally:
        await client.aclose()

    # Determine next version
    latest = (
        await session.execute(
            select(ProposedPipelineRow.version)
            .where(ProposedPipelineRow.project_id == project_id)
            .order_by(desc(ProposedPipelineRow.version))
            .limit(1)
        )
    ).scalar_one_or_none()
    next_version = (latest or 0) + 1

    row = ProposedPipelineRow(
        project_id=project_id,
        version=next_version,
        dag_json=plan.model_dump(mode="json"),
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)

    return success(
        data=_serialize(row),
        message="plan created",
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/plan")
async def get_latest_plan(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    await get_project(session, project_id)
    row = (
        await session.execute(
            select(ProposedPipelineRow)
            .where(ProposedPipelineRow.project_id == project_id)
            .order_by(desc(ProposedPipelineRow.version))
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="no plan yet for this project")
    return success(data=_serialize(row))


# ---------------- Phase 5.3 — pre-label assistant ----------------


def _golden_kind(side: str) -> AssetKind:
    return AssetKind.GOLDEN_TOP if side == "top" else AssetKind.GOLDEN_BOTTOM


def _serialize_prelabel(row: PreLabel) -> dict:
    return {
        "id": str(row.id),
        "project_id": str(row.project_id),
        "side": row.side,
        "regions": row.regions_json,
        "created_at": row.created_at.isoformat(),
    }


@router.post(
    "/prelabel",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_user)],
)
async def create_prelabel(
    project_id: uuid.UUID,
    side: str,
    session: AsyncSession = Depends(get_session),
):
    if side not in ("top", "bottom"):
        raise HTTPException(
            status_code=422, detail=f"side must be 'top' or 'bottom', got {side!r}"
        )

    await get_project(session, project_id)

    bom_rows = (
        await session.execute(
            select(BomItem)
            .where(BomItem.project_id == project_id)
            .order_by(BomItem.designator)
        )
    ).scalars().all()
    if not bom_rows:
        raise HTTPException(
            status_code=422, detail="project has no bom_items; upload a BOM first"
        )

    golden = (
        await session.execute(
            select(Asset)
            .where(
                Asset.project_id == project_id,
                Asset.kind == _golden_kind(side),
            )
            .order_by(desc(Asset.uploaded_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    if golden is None:
        raise HTTPException(
            status_code=422,
            detail=f"project has no golden_{side} asset; upload one before pre-label",
        )

    drawing = (
        await session.execute(
            select(Asset)
            .where(Asset.project_id == project_id, Asset.kind == AssetKind.DRAWING)
            .order_by(desc(Asset.uploaded_at))
            .limit(1)
        )
    ).scalar_one_or_none()

    golden_bytes = absolute_path(golden).read_bytes()
    drawing_bytes = absolute_path(drawing).read_bytes() if drawing is not None else None

    cfg = get_config()
    client = _llm_client_factory(base_url=cfg.ollama_url, timeout=cfg.ollama_timeout)
    try:
        try:
            regions = await prelabel_designators(
                client=client,
                model=cfg.ollama_model_prelabel,
                bom_designators=[r.designator for r in bom_rows],
                golden_image=golden_bytes,
                drawing_image=drawing_bytes,
                side=side,
            )
        except (LlmConnectionError, LlmTimeoutError, LlmResponseError) as exc:
            raise HTTPException(status_code=502, detail=f"Ollama unavailable: {exc}")
        except LlmValidationError as exc:
            raise HTTPException(
                status_code=502, detail=f"Ollama returned invalid pre-label: {exc}"
            )
    finally:
        await client.aclose()

    # Latest-wins UPSERT: drop any existing row for this (project, side) then insert.
    existing = (
        await session.execute(
            select(PreLabel).where(
                PreLabel.project_id == project_id,
                PreLabel.side == side,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        await session.delete(existing)
        await session.flush()

    row = PreLabel(
        project_id=project_id,
        side=side,
        regions_json=[r.model_dump(mode="json") for r in regions],
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)

    return success(
        data=_serialize_prelabel(row),
        message="pre-label saved",
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/prelabel")
async def get_latest_prelabel(
    project_id: uuid.UUID,
    side: str,
    session: AsyncSession = Depends(get_session),
):
    if side not in ("top", "bottom"):
        raise HTTPException(
            status_code=422, detail=f"side must be 'top' or 'bottom', got {side!r}"
        )
    await get_project(session, project_id)
    row = (
        await session.execute(
            select(PreLabel).where(
                PreLabel.project_id == project_id,
                PreLabel.side == side,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"no pre-label yet for side={side}"
        )
    return success(data=_serialize_prelabel(row))
