"""Request/response schemas for the LLM routes."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from indusia_visual_editor.services.llm.schemas import ProposedPipeline


class ProposedPipelineRead(BaseModel):
    """Wrapped response for `GET/POST /api/projects/{id}/llm/plan`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    version: int
    plan: ProposedPipeline
    created_at: datetime
