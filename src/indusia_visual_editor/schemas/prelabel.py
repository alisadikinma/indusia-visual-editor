"""Request/response schemas for the pre-label route."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from indusia_visual_editor.services.llm.schemas import PreLabeledRegion


class PreLabelRunRead(BaseModel):
    """Response shape for POST/GET `/api/projects/{id}/llm/prelabel`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    side: Literal["top", "bottom"]
    regions: list[PreLabeledRegion]
    created_at: datetime
