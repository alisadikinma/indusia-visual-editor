"""Request/response schemas for the labeling routes."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class LabelSubmit(BaseModel):
    """POST /api/projects/{id}/labels body — the raw LSF annotation."""

    model_config = ConfigDict(extra="ignore")

    ls_json: dict[str, Any]


class LabelRead(BaseModel):
    """Response shape for POST/GET label endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    side: Literal["top", "bottom"]
    version: int
    snapshot_at: datetime
