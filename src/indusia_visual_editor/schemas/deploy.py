"""Response schema for the M10 deploy surface (Phase 10.3)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DeploymentRead(BaseModel):
    """Shape returned by `POST /api/projects/{id}/deploy` + GET history."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    train_run_id: uuid.UUID
    model_version: str
    status: str
    edges_notified: dict | None
    deployed_at: datetime
    error_text: str | None
