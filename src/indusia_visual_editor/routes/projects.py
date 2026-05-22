"""Projects CRUD: POST, GET-list, GET-one, PUT, DELETE.

All responses use the canonical `{status, message, data}` envelope via
`utils.responses`. Errors map to 404 / 409 / 422 with the same envelope
shape (see exception handlers in main.py).
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from indusia_visual_editor.db.session import get_session
from indusia_visual_editor.schemas.projects import (
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
)
from indusia_visual_editor.services.project.crud import (
    create_project,
    delete_project,
    get_project,
    list_projects,
    update_project,
)
from indusia_visual_editor.utils.responses import success


router = APIRouter(prefix="/api/projects", tags=["projects"])


def _serialize(project) -> dict:
    return ProjectRead.model_validate(project).model_dump(mode="json")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project_route(
    payload: ProjectCreate,
    session: AsyncSession = Depends(get_session),
):
    project = await create_project(session, payload)
    return success(
        data=_serialize(project),
        message="project created",
        status_code=status.HTTP_201_CREATED,
    )


@router.get("")
async def list_projects_route(session: AsyncSession = Depends(get_session)):
    projects = await list_projects(session)
    return success(data=[_serialize(p) for p in projects])


@router.get("/{project_id}")
async def get_project_route(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    project = await get_project(session, project_id)
    return success(data=_serialize(project))


@router.put("/{project_id}")
async def update_project_route(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    session: AsyncSession = Depends(get_session),
):
    project = await update_project(session, project_id, payload)
    return success(data=_serialize(project), message="project updated")


@router.delete("/{project_id}")
async def delete_project_route(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    await delete_project(session, project_id)
    return success(message="project deleted")
