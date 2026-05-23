"""Request/response schemas for the training route (Phase 7.3+)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class TrainRunRead(BaseModel):
    """Response shape for `/api/projects/{id}/training/start` + history GET."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    adapt_run_id: uuid.UUID
    service_job_id: str
    status: Literal["pending", "running", "succeeded", "failed", "cancelled"]
    metrics_json: dict[str, Any] | None
    started_at: datetime
    ended_at: datetime | None
    error_text: str | None
