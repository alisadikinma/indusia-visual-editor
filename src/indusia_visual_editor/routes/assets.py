"""Asset upload + serve + list routes.

POST   /api/projects/{project_id}/assets?kind=<AssetKind>      201 / 200 (dedup)
GET    /api/projects/{project_id}/assets                       200 list
GET    /api/projects/{project_id}/assets/{asset_id}/binary     200 file bytes

`kind` is validated as the AssetKind enum (Query param) — wrong values yield
422 with the canonical envelope. Size cap (IVE_MAX_ASSET_BYTES) yields 413.
"""

import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from indusia_visual_editor.db.models import AssetKind
from indusia_visual_editor.db.session import get_session
from indusia_visual_editor.schemas.assets import AssetRead
from indusia_visual_editor.services.asset.image_store import (
    absolute_path,
    get_asset,
    list_assets,
    save_asset,
)
from indusia_visual_editor.services.project.crud import get_project
from indusia_visual_editor.utils.responses import success


router = APIRouter(prefix="/api/projects/{project_id}/assets", tags=["assets"])


def _serialize(asset) -> dict:
    return AssetRead.model_validate(asset).model_dump(mode="json")


@router.post("")
async def upload_asset(
    project_id: uuid.UUID,
    kind: AssetKind = Query(...),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    await get_project(session, project_id)  # raises 404 if missing

    file_bytes = await file.read()
    asset, created = await save_asset(
        session=session,
        project_id=project_id,
        kind=kind,
        file_bytes=file_bytes,
        filename=file.filename or "upload.bin",
        mime=file.content_type,
    )
    return success(
        data=_serialize(asset),
        message="asset uploaded" if created else "asset already exists",
        status_code=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@router.get("")
async def list_assets_route(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    await get_project(session, project_id)
    rows = await list_assets(session, project_id)
    return success(data=[_serialize(a) for a in rows])


@router.get("/{asset_id}/binary")
async def get_asset_binary(
    project_id: uuid.UUID,
    asset_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    asset = await get_asset(session, project_id, asset_id)
    file_path = absolute_path(asset)
    return FileResponse(
        path=file_path,
        media_type=asset.mime or "application/octet-stream",
        filename=file_path.name,
    )
