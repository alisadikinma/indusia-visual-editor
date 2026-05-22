"""CRUD for the Project aggregate.

Errors are typed so routes can map them to specific HTTP status codes
without leaking ORM internals:
- DuplicateSlugError → 409 Conflict
- ProjectNotFoundError → 404 Not Found
Validation errors are surfaced by pydantic upstream (422).
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from indusia_visual_editor.db.models import Project
from indusia_visual_editor.schemas.projects import ProjectCreate, ProjectUpdate


class DuplicateSlugError(Exception):
    """Raised when a slug already exists in the projects table."""


class ProjectNotFoundError(Exception):
    """Raised when a project_id has no matching row."""


async def create_project(session: AsyncSession, payload: ProjectCreate) -> Project:
    project = Project(name=payload.name, slug=payload.slug)
    session.add(project)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise DuplicateSlugError(payload.slug) from exc
    await session.refresh(project)
    return project


async def list_projects(session: AsyncSession) -> Sequence[Project]:
    result = await session.execute(select(Project).order_by(Project.created_at.desc()))
    return result.scalars().all()


async def get_project(session: AsyncSession, project_id: uuid.UUID) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError(str(project_id))
    return project


async def update_project(
    session: AsyncSession, project_id: uuid.UUID, payload: ProjectUpdate
) -> Project:
    project = await get_project(session, project_id)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(project, field, value)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise DuplicateSlugError(updates.get("slug", "")) from exc
    await session.refresh(project)
    return project


async def delete_project(session: AsyncSession, project_id: uuid.UUID) -> None:
    project = await get_project(session, project_id)
    await session.delete(project)
    await session.flush()
