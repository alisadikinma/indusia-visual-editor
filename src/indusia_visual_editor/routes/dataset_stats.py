"""Phase 8.1 — dataset stats endpoint for the Gate-1 training-approval panel.

GET /api/projects/{project_id}/dataset/stats?side=top|bottom

Reads the latest `Label` row for the given side, walks its LS-JSON via
`derive_inspect_scope`, and joins back to `bom_items` for the MI-likely /
SMT split. Returns the counts the operator sees on the "Mulai Training"
panel before they hand off to `POST /api/projects/{id}/training/start`
(Phase 7.3).

Stats reflect REAL `bom_items` joins, not fabricated counts: every number
either traces to an LS-JSON region or to a row in `bom_items`.

404 if no label exists yet for the requested side (the operator has not
finished the M6 canvas pass — the UI uses this to disable the "Mulai
Training" button).
422 if the side query param is not in {'top','bottom'}.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from indusia_visual_editor.db.models import BomItem, Label
from indusia_visual_editor.db.session import get_session
from indusia_visual_editor.services.inspect_scope.derive import (
    DEFECT_CRITERIA,
    LSAnnotation,
    derive_inspect_scope,
)
from indusia_visual_editor.services.project.crud import get_project
from indusia_visual_editor.utils.responses import success


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/projects/{project_id}/dataset", tags=["dataset"])


def _empty_criteria_counts() -> dict[str, int]:
    """Zero-initialise so the UI always renders the full 9-criterion grid,
    even when the operator hasn't picked any defect criterion yet."""
    return {c: 0 for c in DEFECT_CRITERIA}


async def compute_dataset_stats(
    session: AsyncSession, project_id: uuid.UUID, side: str
) -> dict | None:
    """Walk the latest Label for (project_id, side), derive per-region updates,
    and tally counts. Returns None when there's no label for the side yet —
    callers convert that to whatever HTTP status they prefer (404 for the
    dataset_stats route; 404 for the training/suggest-hyperparams route).

    Shape matches the dataset_stats response `data` field exactly so the
    suggest-hyperparams route can echo it without remapping.
    """
    label = (
        await session.execute(
            select(Label)
            .where(Label.project_id == project_id, Label.side == side)
            .order_by(desc(Label.version))
            .limit(1)
        )
    ).scalar_one_or_none()
    if label is None:
        return None

    annotation = LSAnnotation.model_validate(label.ls_json)
    updates = derive_inspect_scope(annotation)

    bom_rows = (
        await session.execute(
            select(BomItem.designator, BomItem.mi_likely).where(
                BomItem.project_id == project_id
            )
        )
    ).all()
    mi_lookup: dict[str, bool | None] = {d: m for d, m in bom_rows}

    per_criterion = _empty_criteria_counts()
    inspected = 0
    skipped = 0
    mi_count = 0
    smt_count = 0
    designators_out: list[dict] = []

    for u in updates:
        if u.inspect_scope == "inspected":
            inspected += 1
        else:
            skipped += 1

        for crit in u.defect_criteria:
            if crit in per_criterion:
                per_criterion[crit] += 1

        mi_flag = mi_lookup.get(u.designator)
        if mi_flag is True:
            mi_count += 1
        elif mi_flag is False:
            smt_count += 1

        designators_out.append(
            {
                "designator": u.designator,
                "inspect_scope": u.inspect_scope,
                "scope_mode": u.scope_mode,
                "defect_criteria": list(u.defect_criteria),
                "mi_likely": mi_flag,
            }
        )

    return {
        "project_id": str(project_id),
        "side": side,
        "label_version": label.version,
        "total": inspected + skipped,
        "inspected": inspected,
        "skipped": skipped,
        "per_criterion": per_criterion,
        "mi_count": mi_count,
        "smt_count": smt_count,
        "designators": designators_out,
    }


@router.get("/stats")
async def get_dataset_stats(
    project_id: uuid.UUID,
    side: str,
    session: AsyncSession = Depends(get_session),
):
    if side not in ("top", "bottom"):
        raise HTTPException(
            status_code=422, detail=f"side must be 'top' or 'bottom', got {side!r}"
        )

    await get_project(session, project_id)

    data = await compute_dataset_stats(session, project_id, side)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail=f"no label yet for side={side}; finish the canvas pass first",
        )

    return success(data=data)
