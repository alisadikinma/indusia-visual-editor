"""Request/response schemas for the inspection-feedback loop.

The Literal sets here MUST stay in lock-step with the CHECK constraints on
the `inspection_feedback` table (db/models.py + migration 0012):
  - model_verdict ∈ {pass, fail, uncertain}
  - operator_mark ∈ {confirmed, escape, overkill}
  - status        ∈ {new, curated, promoted, dismissed}
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


ModelVerdict = Literal["pass", "fail", "uncertain"]
OperatorMark = Literal["confirmed", "escape", "overkill"]
FeedbackStatus = Literal["new", "curated", "promoted", "dismissed"]


class FeedbackIngest(BaseModel):
    """Metadata accepted by `POST /api/projects/{id}/inspection-feedback`.

    `extra="ignore"` so the edge can send richer telemetry than v1 models
    without breaking ingest. The ROI image (if any) rides as a separate
    multipart file part, NOT a field here.
    """

    model_config = ConfigDict(extra="ignore")

    designator: str | None = None
    model_verdict: ModelVerdict
    operator_mark: OperatorMark
    defect_criterion: str | None = None
    inspection_ts: datetime | None = None
    edge_id: uuid.UUID | None = None
    train_run_id: uuid.UUID | None = None


class FeedbackCurate(BaseModel):
    """Body for `PUT /api/inspection-feedback/{id}` — partial update.

    Both fields optional; only the supplied ones are applied. Used to
    re-classify the operator mark or to walk the status (e.g. dismiss a
    spurious row, or mark it curated before promote)."""

    operator_mark: OperatorMark | None = None
    status: FeedbackStatus | None = None


class FeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    edge_id: uuid.UUID | None
    train_run_id: uuid.UUID | None
    designator: str | None
    model_verdict: ModelVerdict
    operator_mark: OperatorMark
    defect_criterion: str | None
    roi_path: str | None
    roi_sha256: str | None
    status: FeedbackStatus
    inspection_ts: datetime | None
    created_at: datetime


class DefectExampleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    source_feedback_id: uuid.UUID | None
    designator: str | None
    defect_criterion: str
    roi_path: str
    roi_sha256: str
    created_at: datetime
