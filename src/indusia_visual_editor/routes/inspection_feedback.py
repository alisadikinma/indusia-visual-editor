"""Inspection-feedback loop routes (v1 runtime feedback).

POST /api/projects/{project_id}/inspection-feedback   201 — ingest a verdict
GET  /api/projects/{project_id}/inspection-feedback    200 — list (?status=)
PUT  /api/inspection-feedback/{feedback_id}            200 — curate mark/status
POST /api/inspection-feedback/{feedback_id}/promote    201 — curate → example

Promote enforces the inspection-logic gate (CLAUDE.md §8 + the loop spec):
a feedback row is promotable to a training `DefectExample` ONLY when

    operator_mark == 'escape'                 (a real missed defect)
    AND defect_criterion ∈ the 9 canonical keys
    AND roi_path is present                    (we have the crop to train on)

`overkill` is a hard-negative — a false alarm, NOT a defect example — so it
is rejected with 409. Missing ROI or an unknown criterion also yield 409.
"""

from __future__ import annotations

import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from indusia_visual_editor.db.models import DefectExample, InspectionFeedback
from indusia_visual_editor.db.session import get_session
from indusia_visual_editor.schemas.inspection_feedback import (
    DefectClassCount,
    DefectExampleRead,
    FeedbackCurate,
    FeedbackIngest,
    FeedbackRead,
)
from indusia_visual_editor.services.auth.dependencies import get_current_user
from indusia_visual_editor.services.feedback.roi_store import save_roi
from indusia_visual_editor.services.project.crud import get_project
from indusia_visual_editor.utils.logging_config import get_logger
from indusia_visual_editor.utils.responses import success


logger = get_logger(__name__)


_MAPPING_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "defect_detector_mapping.yaml"
)

# Supervised per-class data floor — the rough number of real examples a defect
# class needs before a supervised per-class detector is worth training
# (ai-visual-inspection-expert §10). Per-PCB; informational on the rollup.
SUPERVISED_PER_CLASS_FLOOR = 100


@lru_cache(maxsize=1)
def _valid_criteria() -> frozenset[str]:
    """The canonical defect criteria — the keys of the detector mapping.

    Single source of truth: data/defect_detector_mapping.yaml. A promote is
    refused if the row's criterion is not one of these keys."""
    with _MAPPING_PATH.open("r", encoding="utf-8") as fh:
        mapping = yaml.safe_load(fh) or {}
    return frozenset(mapping.keys())


# Routes for a single feedback row live at the app root (no project prefix)
# because curate/promote act on a feedback id directly.
project_router = APIRouter(
    prefix="/api/projects/{project_id}/inspection-feedback",
    tags=["inspection-feedback"],
)
router = APIRouter(prefix="/api/inspection-feedback", tags=["inspection-feedback"])
examples_router = APIRouter(prefix="/api/defect-examples", tags=["inspection-feedback"])


def _serialize(row: InspectionFeedback) -> dict[str, Any]:
    return FeedbackRead.model_validate(row).model_dump(mode="json")


def _serialize_example(row: DefectExample) -> dict[str, Any]:
    return DefectExampleRead.model_validate(row).model_dump(mode="json")


@project_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_user)],
)
async def ingest_feedback(
    project_id: uuid.UUID,
    model_verdict: str = Form(...),
    operator_mark: str = Form(...),
    designator: str | None = Form(None),
    defect_criterion: str | None = Form(None),
    inspection_ts: str | None = Form(None),
    edge_id: uuid.UUID | None = Form(None),
    train_run_id: uuid.UUID | None = Form(None),
    file: UploadFile | None = File(None),
    session: AsyncSession = Depends(get_session),
):
    await get_project(session, project_id)  # raises 404 if missing

    # Coerce + validate the form metadata through the ingest schema so the
    # Literal sets, datetime parsing, and UUID parsing match every other
    # entry point. A bad operator_mark / verdict raises ValidationError here,
    # mapped to the 422 envelope by the global handler.
    try:
        ingest = FeedbackIngest(
            designator=designator,
            model_verdict=model_verdict,
            operator_mark=operator_mark,
            defect_criterion=defect_criterion,
            inspection_ts=inspection_ts,
            edge_id=edge_id,
            train_run_id=train_run_id,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="validation failed") from exc

    roi_path: str | None = None
    roi_sha256: str | None = None
    if file is not None:
        file_bytes = await file.read()
        roi_path, roi_sha256 = save_roi(
            project_id=project_id,
            file_bytes=file_bytes,
            filename=file.filename or "roi.bin",
            mime=file.content_type,
        )

    row = InspectionFeedback(
        project_id=project_id,
        edge_id=ingest.edge_id,
        train_run_id=ingest.train_run_id,
        designator=ingest.designator,
        model_verdict=ingest.model_verdict,
        operator_mark=ingest.operator_mark,
        defect_criterion=ingest.defect_criterion,
        roi_path=roi_path,
        roi_sha256=roi_sha256,
        inspection_ts=ingest.inspection_ts,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return success(
        data=_serialize(row),
        message="feedback recorded",
        status_code=status.HTTP_201_CREATED,
    )


@project_router.get("")
async def list_feedback(
    project_id: uuid.UUID,
    status_filter: str | None = Query(None, alias="status"),
    session: AsyncSession = Depends(get_session),
):
    await get_project(session, project_id)
    stmt = select(InspectionFeedback).where(
        InspectionFeedback.project_id == project_id
    )
    if status_filter is not None:
        stmt = stmt.where(InspectionFeedback.status == status_filter)
    stmt = stmt.order_by(InspectionFeedback.created_at.desc())
    rows = (await session.execute(stmt)).scalars().all()
    return success(data=[_serialize(r) for r in rows])


@router.get("")
async def list_all_feedback(
    status_filter: str | None = Query(None, alias="status"),
    session: AsyncSession = Depends(get_session),
):
    """Cross-project feedback inbox (powers the global `/feedback` screen).

    The S7 screen is reached from the workspace nav, not from inside a single
    project, so it lists feedback across every project. Public in v1, same as
    the project-scoped list."""
    stmt = select(InspectionFeedback)
    if status_filter is not None:
        stmt = stmt.where(InspectionFeedback.status == status_filter)
    stmt = stmt.order_by(InspectionFeedback.created_at.desc())
    rows = (await session.execute(stmt)).scalars().all()
    return success(data=[_serialize(r) for r in rows])


@router.put("/{feedback_id}", dependencies=[Depends(get_current_user)])
async def curate_feedback(
    feedback_id: uuid.UUID,
    body: FeedbackCurate,
    session: AsyncSession = Depends(get_session),
):
    row = await session.get(InspectionFeedback, feedback_id)
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"feedback {feedback_id} not found"
        )
    if body.operator_mark is not None:
        row.operator_mark = body.operator_mark
    if body.status is not None:
        row.status = body.status
    await session.flush()
    await session.refresh(row)
    return success(data=_serialize(row))


@router.post(
    "/{feedback_id}/promote",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_user)],
)
async def promote_feedback(
    feedback_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Promote a confirmed missed-defect into a curated `DefectExample`.

    Enforces the inspection-logic gate before creating the training sample.
    """
    row = await session.get(InspectionFeedback, feedback_id)
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"feedback {feedback_id} not found"
        )

    if row.status == "promoted":
        raise HTTPException(
            status_code=409,
            detail="feedback already promoted to a defect example",
        )
    if row.operator_mark != "escape":
        raise HTTPException(
            status_code=409,
            detail=(
                "only an 'escape' (real missed defect) is promotable; "
                f"this row is marked {row.operator_mark!r} — 'overkill' is a "
                "hard-negative, not a defect example"
            ),
        )
    if not row.roi_path or not row.roi_sha256:
        raise HTTPException(
            status_code=409,
            detail="cannot promote without a stored ROI crop",
        )
    if row.defect_criterion not in _valid_criteria():
        raise HTTPException(
            status_code=409,
            detail=(
                f"defect_criterion {row.defect_criterion!r} is not one of the "
                f"canonical criteria {sorted(_valid_criteria())}"
            ),
        )

    example = DefectExample(
        project_id=row.project_id,
        source_feedback_id=row.id,
        designator=row.designator,
        defect_criterion=row.defect_criterion,
        roi_path=row.roi_path,
        roi_sha256=row.roi_sha256,
    )
    session.add(example)
    row.status = "promoted"
    await session.flush()
    await session.refresh(example)
    return success(
        data=_serialize_example(example),
        message="defect example created",
        status_code=status.HTTP_201_CREATED,
    )


@examples_router.get("/summary")
async def defect_library_summary(
    project_id: uuid.UUID | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """Per-class inventory of the promoted defect library (surface S8).

    Returns one row per canonical criterion (zero-filled), so the Datasets card
    shows every class. `?project_id=` scopes to one PCB (where the per-class
    floor is meaningful, since models train per-PCB); without it the counts are
    a cross-project library rollup. Public, same as the other reads. The
    examples are NOT yet consumed by training — this is an accumulation queue,
    not an active training signal."""
    stmt = select(
        DefectExample.defect_criterion, func.count()
    ).group_by(DefectExample.defect_criterion)
    if project_id is not None:
        stmt = stmt.where(DefectExample.project_id == project_id)
    counts = {
        criterion: total for criterion, total in (await session.execute(stmt)).all()
    }
    rows = [
        DefectClassCount(
            defect_criterion=criterion,
            count=counts.get(criterion, 0),
            meets_floor=counts.get(criterion, 0) >= SUPERVISED_PER_CLASS_FLOOR,
        ).model_dump(mode="json")
        for criterion in sorted(_valid_criteria())
    ]
    return success(
        data={"floor": SUPERVISED_PER_CLASS_FLOOR, "classes": rows},
        message="defect library inventory",
    )
