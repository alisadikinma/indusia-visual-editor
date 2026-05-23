"""Request/response schemas for the edges registry (Phase 11.1 + 11.3)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class EdgeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    webhook_url: HttpUrl
    version_policy: dict[str, Any] | None = None


class EdgeUpdate(BaseModel):
    """Body for `PUT /api/edges/{id}` — partial update of policy only.

    name + webhook_url are immutable post-registration; updating those
    requires deleting and re-registering so the audit trail is clean.
    """

    version_policy: dict[str, Any]


class EdgePin(BaseModel):
    """Body for `PUT /api/edges/{id}/pin` (Phase 11.3).

    When both `model_name` and `version` are supplied → pinned mode.
    When both are absent → reset to `auto_pull_latest` (the unpin path).
    Either both or neither is enforced server-side.
    """

    model_name: str | None = None
    version: str | None = None


class EdgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    webhook_url: str
    version_policy: dict[str, Any]
    registered_at: datetime
    last_seen_at: datetime | None
