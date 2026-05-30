"""Labeling canvas routes — feeds and consumes the LSF (Label Studio Frontend) embed.

GET  /api/projects/{project_id}/labels/task?side=top|bottom
  Composes the LSF task JSON used by the canvas:
    - data.image       relative URL to the asset binary endpoint
    - predictions[]    baked from the latest pre_labels row (M5 output)
    - annotations[]    empty array — operator fills via the canvas
  And the XML labeling config built from this project's BOM
  designators (one <Label> per designator), per-region inspect_scope +
  scope_mode + defect_criteria choice sets.

  422 if the project has no BOM rows or no golden_<side> asset.
  422 if `side` is anything other than 'top' or 'bottom'.

POST /api/projects/{project_id}/labels?side=top|bottom
  Body: {"ls_json": <full LSF annotation>}
  Validates via `LSAnnotation`, runs `derive_inspect_scope`, propagates
  per-region inspect_scope back to bom_items rows, then persists the
  full annotation as a new version in `labels`.

  Versions are per (project_id, side) — top v1 and bottom v1 coexist.
  Re-submitting bumps the version, never overwrites.

  422 on malformed ls_json, unknown defect criterion, invalid scope_mode,
  or solder_short used outside whole_side scope.

The LSF embed itself is M6 Phase 6.4 (LSFEmbed.vue). This route only
emits and consumes JSON — never invokes LSF.
"""

from __future__ import annotations

import html
import uuid
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from indusia_visual_editor.db.models import (
    Asset,
    AssetKind,
    BomItem,
    InspectScope,
    Label,
    PreLabel,
)
from indusia_visual_editor.db.session import get_session
from indusia_visual_editor.services.auth.dependencies import get_current_user
from indusia_visual_editor.services.inspect_scope.derive import (
    DEFECT_CRITERIA,
    LSAnnotation,
    UnknownDefectCriterion,
    derive_inspect_scope,
)
from indusia_visual_editor.services.project.crud import get_project
from indusia_visual_editor.utils.responses import success


router = APIRouter(prefix="/api/projects/{project_id}/labels", tags=["labels"])


# ---------- helpers ----------


def _check_side(side: str) -> None:
    if side not in ("top", "bottom"):
        raise HTTPException(
            status_code=422, detail=f"side must be 'top' or 'bottom', got {side!r}"
        )


def _golden_kind(side: str) -> AssetKind:
    return AssetKind.GOLDEN_TOP if side == "top" else AssetKind.GOLDEN_BOTTOM


async def _latest_asset(
    session: AsyncSession, project_id: uuid.UUID, kind: AssetKind
) -> Asset | None:
    return (
        await session.execute(
            select(Asset)
            .where(Asset.project_id == project_id, Asset.kind == kind)
            .order_by(desc(Asset.uploaded_at))
            .limit(1)
        )
    ).scalar_one_or_none()


async def _load_bom(session: AsyncSession, project_id: uuid.UUID) -> list[BomItem]:
    return list(
        (
            await session.execute(
                select(BomItem)
                .where(BomItem.project_id == project_id)
                .order_by(BomItem.designator)
            )
        ).scalars().all()
    )


async def _latest_prelabel(
    session: AsyncSession, project_id: uuid.UUID, side: str
) -> PreLabel | None:
    return (
        await session.execute(
            select(PreLabel).where(
                PreLabel.project_id == project_id, PreLabel.side == side
            )
        )
    ).scalar_one_or_none()


def _attr(value: str) -> str:
    """Escape a value for use inside an XML attribute (double-quoted)."""
    return html.escape(value, quote=True)


def _build_config_xml(designators: list[str]) -> str:
    """Compose the LSF labeling config.

    Layout: one <RectangleLabels> with a <Label> per BOM designator + three
    perRegion <Choices> blocks for inspect_scope, scope_mode, defect_criteria.
    Stays declarative — no Jinja, no runtime templating concerns.
    """
    label_tags = "".join(
        f'<Label value="{_attr(d)}" />' for d in designators
    )
    criteria_tags = "".join(
        f'<Choice value="{_attr(c)}" />' for c in DEFECT_CRITERIA
    )
    return (
        "<View>"
        '<Image name="image" value="$image" zoom="true" zoomControl="true" '
        'rotateControl="false" />'
        '<RectangleLabels name="label" toName="image">'
        f"{label_tags}"
        "</RectangleLabels>"
        '<Choices name="inspect_scope" toName="image" perRegion="true" '
        'showInline="true">'
        '<Choice value="inspected" />'
        '<Choice value="skipped" />'
        "</Choices>"
        '<Choices name="scope_mode" toName="image" perRegion="true" '
        'showInline="true">'
        '<Choice value="per_component" />'
        '<Choice value="whole_side" />'
        "</Choices>"
        '<Choices name="defect_criteria" toName="image" perRegion="true" '
        'choice="multiple" showInline="true">'
        f"{criteria_tags}"
        "</Choices>"
        "</View>"
    )


def _prelabel_to_lsf_predictions(
    prelabel: PreLabel | None, project_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Translate normalized PreLabel regions into LSF predictions[]."""
    if prelabel is None or not prelabel.regions_json:
        return []
    result: list[dict[str, Any]] = []
    avg_conf = 0.0
    for region in prelabel.regions_json:
        bbox = region.get("bbox") or [0, 0, 0, 0]
        nx, ny, nw, nh = (float(b) for b in bbox)
        conf = float(region.get("confidence", 0.0))
        result.append(
            {
                # Stable per-region ID — LSF will treat each as a separate
                # editable region. We use uuid4 so re-fetching the same task
                # in two tabs doesn't collide. (The pre_labels row itself is
                # what persists the bbox; this id is canvas-local.)
                "id": uuid.uuid4().hex[:10],
                "type": "rectanglelabels",
                "from_name": "label",
                "to_name": "image",
                "image_rotation": 0,
                "original_width": 1000,
                "original_height": 1000,
                # Per-region confidence (0–1) carried through so the canvas
                # can flag low-confidence predictions for operator review (S4).
                "score": conf,
                "value": {
                    "x": nx * 100.0,
                    "y": ny * 100.0,
                    "width": nw * 100.0,
                    "height": nh * 100.0,
                    "rotation": 0,
                    "rectanglelabels": [str(region.get("designator", ""))],
                },
            }
        )
        avg_conf += conf
    return [
        {
            "model_version": "prelabel-v1",
            "score": (avg_conf / len(prelabel.regions_json)) if prelabel.regions_json else 0.0,
            "result": result,
        }
    ]


# ---------- GET task ----------


@router.get("/task")
async def get_task(
    project_id: uuid.UUID,
    side: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    _check_side(side)
    await get_project(session, project_id)

    bom_rows = await _load_bom(session, project_id)
    if not bom_rows:
        raise HTTPException(
            status_code=422,
            detail="project has no bom_items; upload a BOM first",
        )

    golden = await _latest_asset(session, project_id, _golden_kind(side))
    if golden is None:
        raise HTTPException(
            status_code=422,
            detail=f"project has no golden_{side} asset; upload one before labeling",
        )

    prelabel = await _latest_prelabel(session, project_id, side)

    designators = [b.designator for b in bom_rows]
    config_xml = _build_config_xml(designators)
    image_url = f"/api/projects/{project_id}/assets/{golden.id}/binary"

    task = {
        "id": 1,  # LSF requires a numeric task id even for single-task mode
        "data": {"image": image_url},
        "predictions": _prelabel_to_lsf_predictions(prelabel, project_id),
        "annotations": [],
    }

    return success(
        data={
            "config": config_xml,
            "task": task,
            "side": side,
            "designator_count": len(designators),
        },
        message="task ready",
    )


# ---------- POST submit ----------


def _serialize_label(row: Label) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "project_id": str(row.project_id),
        "side": row.side,
        "version": row.version,
        "snapshot_at": row.snapshot_at.isoformat(),
    }


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_user)],
)
async def submit_labels(
    project_id: uuid.UUID,
    side: str = Query(...),
    payload: dict[str, Any] = Body(...),
    session: AsyncSession = Depends(get_session),
):
    _check_side(side)
    await get_project(session, project_id)

    ls_json_raw = payload.get("ls_json")
    if not isinstance(ls_json_raw, dict):
        raise HTTPException(
            status_code=422,
            detail="payload.ls_json missing or not an object",
        )

    try:
        annotation = LSAnnotation.model_validate(ls_json_raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422, detail=f"ls_json failed validation: {exc.errors()}"
        )

    try:
        updates = derive_inspect_scope(annotation)
    except UnknownDefectCriterion as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Propagate per-region derived values onto bom_items. Phase 6.6 added
    # scope_mode + detector_presets columns; we write all three here.
    if updates:
        bom_rows = await _load_bom(session, project_id)
        by_des = {b.designator: b for b in bom_rows}
        for upd in updates:
            row = by_des.get(upd.designator)
            if row is None:
                # Annotation references a designator not in BOM — skip silently.
                # The canvas <Label> set is derived from BOM, so this normally
                # cannot happen except via tampered submits.
                continue
            row.inspect_scope = InspectScope(upd.inspect_scope)
            row.scope_mode = upd.scope_mode
            row.detector_presets = list(upd.detector_presets)

    # Next version per (project, side).
    latest = (
        await session.execute(
            select(Label.version)
            .where(Label.project_id == project_id, Label.side == side)
            .order_by(desc(Label.version))
            .limit(1)
        )
    ).scalar_one_or_none()
    next_version = (latest or 0) + 1

    label_row = Label(
        project_id=project_id,
        side=side,
        version=next_version,
        ls_json=ls_json_raw,
    )
    session.add(label_row)
    await session.flush()
    await session.refresh(label_row)

    return success(
        data=_serialize_label(label_row),
        message="labels saved",
        status_code=status.HTTP_201_CREATED,
    )


@router.get("")
async def get_labels_history(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    await get_project(session, project_id)
    rows = (
        await session.execute(
            select(Label)
            .where(Label.project_id == project_id)
            .order_by(Label.side, desc(Label.version))
        )
    ).scalars().all()
    return success(data=[_serialize_label(r) for r in rows])
