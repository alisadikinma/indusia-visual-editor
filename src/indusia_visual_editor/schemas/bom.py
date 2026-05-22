"""Pydantic schemas for the BOM items API."""

import uuid

from pydantic import BaseModel, ConfigDict

from indusia_visual_editor.db.models import InspectScope


class BomItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    designator: str
    value: str | None
    package: str | None
    qty: int | None
    position_hint: str | None
    inspect_scope: InspectScope
    mi_likely: bool | None
    component_type: str | None
    defect_history_count: int
    extra: dict | None
