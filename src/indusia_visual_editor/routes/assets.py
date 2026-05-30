"""Asset upload + serve + list routes.

POST   /api/projects/{project_id}/assets?kind=<AssetKind>      201 / 200 (dedup)
GET    /api/projects/{project_id}/assets                       200 list
GET    /api/projects/{project_id}/assets/{asset_id}/binary     200 file bytes

`kind` is validated as the AssetKind enum (Query param) — wrong values yield
422 with the canonical envelope. Size cap (IVE_MAX_ASSET_BYTES) yields 413.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from indusia_visual_editor.db.models import AssetKind
from indusia_visual_editor.db.session import get_session
from indusia_visual_editor.schemas.assets import AssetRead
from indusia_visual_editor.services.asset.golden_qc import (
    GoldenQcError,
    assess_golden_qc,
)
from indusia_visual_editor.services.asset.image_store import (
    absolute_path,
    get_asset,
    list_assets,
    save_asset,
)
from indusia_visual_editor.services.asset.registration import (
    RegistrationError,
    assess_registration,
)
from indusia_visual_editor.services.auth.dependencies import get_current_user
from indusia_visual_editor.services.project.crud import get_project
from indusia_visual_editor.utils.responses import success


router = APIRouter(prefix="/api/projects/{project_id}/assets", tags=["assets"])
preflight_router = APIRouter(prefix="/api/projects/{project_id}", tags=["assets"])

_GOLDEN_KINDS = {AssetKind.GOLDEN_TOP, AssetKind.GOLDEN_BOTTOM}


def _golden_kind(side: str) -> AssetKind:
    if side == "top":
        return AssetKind.GOLDEN_TOP
    if side == "bottom":
        return AssetKind.GOLDEN_BOTTOM
    raise HTTPException(status_code=422, detail="side must be 'top' or 'bottom'")


def _serialize(asset) -> dict:
    return AssetRead.model_validate(asset).model_dump(mode="json")


def _is_golden_image(kind: AssetKind, mime: str | None) -> bool:
    return kind in _GOLDEN_KINDS and bool(mime) and mime.startswith("image/")


def _qc_or_none(file_bytes: bytes) -> dict[str, Any]:
    """Run golden QC, mapping undecodable bytes to a fail verdict rather than
    raising — a bad upload should warn the operator, not 500 the request."""
    try:
        return assess_golden_qc(file_bytes)
    except GoldenQcError:
        return {
            "verdict": "fail",
            "reasons": ["undecodable"],
            "sharpness": 0.0,
            "mean_luminance": 0.0,
            "clipped_dark": 0.0,
            "clipped_bright": 0.0,
        }


@router.post("", dependencies=[Depends(get_current_user)])
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
    data = _serialize(asset)
    if _is_golden_image(kind, asset.mime):
        data["qc"] = _qc_or_none(file_bytes)
    return success(
        data=data,
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


@router.get("/{asset_id}/qc")
async def get_asset_qc(
    project_id: uuid.UUID,
    asset_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Recompute golden-sample QC from the stored image (T6 / G4).

    Deterministic from the bytes on disk, so no QC column is persisted. 422
    if the asset is not a golden image."""
    asset = await get_asset(session, project_id, asset_id)
    if not _is_golden_image(asset.kind, asset.mime):
        raise HTTPException(
            status_code=422,
            detail="QC only applies to golden_top/golden_bottom image assets",
        )
    file_bytes = absolute_path(asset).read_bytes()
    return success(data=_qc_or_none(file_bytes), message="golden QC")


@preflight_router.get("/registration-preflight")
async def registration_preflight(
    project_id: uuid.UUID,
    side: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Pre-flight the golden sample(s) for a side (T7 / G2).

    Relative pixel-domain check (feature-detectability + pairwise residual),
    NOT absolute µm registration. 422 if the side has no golden yet."""
    await get_project(session, project_id)
    kind = _golden_kind(side)
    goldens = [a for a in await list_assets(session, project_id) if a.kind == kind]
    if not goldens:
        raise HTTPException(
            status_code=422, detail=f"no {kind.value} asset uploaded yet"
        )
    images = [absolute_path(a).read_bytes() for a in goldens]
    try:
        result = assess_registration(images)
    except RegistrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return success(data=result, message="registration pre-flight")


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
