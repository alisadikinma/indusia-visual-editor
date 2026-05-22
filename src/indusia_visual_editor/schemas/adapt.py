"""Request/response schemas for the adapter route."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from indusia_visual_editor.services.inspect_scope.derive import LSAnnotation


class AdaptRequest(BaseModel):
    """Body of POST /api/projects/{id}/adapt.

    `lsf_annotation` is the LSF JSON shape — same `result[]` envelope
    that `derive_inspect_scope` already consumes. In M6 the canvas
    will POST this on submit; for now (M4) tests build it synthetically.
    """

    lsf_annotation: LSAnnotation


class AdaptRunRead(BaseModel):
    """One row from the adapt_runs history."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    pcb_name: str
    model_dir: str
    inspected_count: int
    status: str
    created_at: datetime
