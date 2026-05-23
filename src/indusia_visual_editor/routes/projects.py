"""Projects CRUD: POST, GET-list, GET-one, PUT, DELETE.

All mutation routes are protected by the bearer-token gate (Phase 13.3)
and carry role gates layered on top (Phase 13.4):

  POST     engineer + admin
  PUT      engineer + admin
  DELETE   admin only

Listing is scoped by the caller's organization_id when present — engineers
of org A never see org B's rows. The viewer role lands here too (read-only).
GETs stay public in v1 per the Phase 13.3 decision; once SaaS multi-tenant
ships in v1.5, every GET will need the same scope-by-org guard.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from indusia_visual_editor.db.models import User
from indusia_visual_editor.db.session import get_session
from indusia_visual_editor.schemas.projects import (
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
)
from indusia_visual_editor.services.auth.dependencies import (
    get_current_user,
    get_current_user_optional,
    require_role,
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
    current_user: User = Depends(require_role("admin", "engineer")),
    session: AsyncSession = Depends(get_session),
):
    project = await create_project(
        session, payload, organization_id=current_user.organization_id
    )
    return success(
        data=_serialize(project),
        message="project created",
        status_code=status.HTTP_201_CREATED,
    )


@router.get("")
async def list_projects_route(
    session: AsyncSession = Depends(get_session),
    current_user: User | None = Depends(get_current_user_optional),
):
    # GETs are open in v1. When the caller IS authenticated we scope by
    # their org so a logged-in viewer only sees their tenant's rows;
    # otherwise the route returns every project (legacy behaviour kept
    # so /api/projects keeps working before login is wired in 13.5).
    org_id = current_user.organization_id if current_user else None
    projects = await list_projects(session, organization_id=org_id)
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
    current_user: User = Depends(require_role("admin", "engineer")),
    session: AsyncSession = Depends(get_session),
):
    project = await update_project(session, project_id, payload)
    return success(data=_serialize(project), message="project updated")


@router.delete("/{project_id}")
async def delete_project_route(
    project_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
):
    await delete_project(session, project_id)
    return success(message="project deleted")
