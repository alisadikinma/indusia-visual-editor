"""Pydantic schemas for the Projects API."""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from indusia_visual_editor.db.models import ProjectStatus


SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$|^[a-z0-9]$")


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255)

    @field_validator("slug")
    @classmethod
    def slug_is_url_safe(cls, v: str) -> str:
        if not SLUG_PATTERN.match(v):
            raise ValueError(
                "slug must be lowercase alphanumeric with optional hyphens "
                "(no leading/trailing hyphen, no underscores or spaces)"
            )
        return v


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=255)
    status: ProjectStatus | None = None

    @field_validator("slug")
    @classmethod
    def slug_is_url_safe(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not SLUG_PATTERN.match(v):
            raise ValueError(
                "slug must be lowercase alphanumeric with optional hyphens"
            )
        return v


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime
