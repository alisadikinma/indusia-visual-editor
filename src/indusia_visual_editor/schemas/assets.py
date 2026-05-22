"""Pydantic schemas for the Assets API."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from indusia_visual_editor.db.models import AssetKind


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    kind: AssetKind
    path: str
    sha256: str
    mime: str | None
    size_bytes: int | None
    uploaded_at: datetime
