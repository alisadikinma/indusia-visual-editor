"""Filesystem asset storage with SHA256 dedup.

Files live under `<IVE_STORAGE_ROOT>/{project_id}/{kind}/{sha256}.{ext}`.
The on-disk filename is derived ENTIRELY from the SHA256 — the user-
provided filename is only consulted for the extension. This makes path
traversal via filename impossible.

Dedup is per (project_id, sha256) — uploading the same bytes to the same
project returns the existing Asset row.
"""

import hashlib
import mimetypes
import uuid
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from indusia_visual_editor.config import get_config
from indusia_visual_editor.db.models import Asset, AssetKind, BomItem
from indusia_visual_editor.services.asset.bom_parser import parse_bom


class AssetTooLargeError(Exception):
    """Raised when the upload exceeds IVE_MAX_ASSET_BYTES."""


class AssetNotFoundError(Exception):
    """Raised when an asset_id has no matching row."""


def _safe_extension(filename: str, mime: str | None) -> str:
    """Pick a file extension from the upload's metadata. The user filename
    is ONLY consulted for `.ext`; the rest is discarded to neutralize
    path traversal via filenames like `../../etc/passwd`."""
    raw = Path(filename).suffix.lower()
    if raw and len(raw) <= 16 and raw[1:].isalnum():
        return raw
    if mime:
        guessed = mimetypes.guess_extension(mime)
        if guessed:
            return guessed
    return ".bin"


async def save_asset(
    session: AsyncSession,
    project_id: uuid.UUID,
    kind: AssetKind,
    file_bytes: bytes,
    filename: str,
    mime: str | None,
) -> tuple[Asset, bool]:
    """Save the bytes to disk + create (or return existing) Asset row.

    Returns (asset, created) — created=False means a dedup hit occurred and
    no new row was inserted.

    For `kind=AssetKind.BOM`, the bytes are parsed FIRST (validation up-
    front). On success the asset is persisted and the project's bom_items
    are REPLACED with the new drafts (latest BOM wins — Phase 2.2 decision).
    On parse failure, BomParseError propagates and the route maps it to 422
    via the global exception handler; nothing is written to DB or disk.
    """
    config = get_config()
    if len(file_bytes) > config.max_asset_bytes:
        raise AssetTooLargeError(
            f"{len(file_bytes)} bytes exceeds limit {config.max_asset_bytes}"
        )

    # Parse BOM FIRST so a malformed file never touches the DB or disk.
    bom_drafts = None
    if kind == AssetKind.BOM:
        bom_drafts = parse_bom(file_bytes, filename)

    sha256 = hashlib.sha256(file_bytes).hexdigest()

    # Dedup check — same bytes already uploaded? Skip both disk write
    # and bom_items mutation (identical bytes → identical parsed result).
    existing = (
        await session.execute(
            select(Asset).where(
                Asset.project_id == project_id, Asset.sha256 == sha256
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False

    ext = _safe_extension(filename, mime)
    relative_path = f"{project_id}/{kind.value}/{sha256}{ext}"
    target_dir = Path(config.storage_root) / str(project_id) / kind.value
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / f"{sha256}{ext}"

    target_file.write_bytes(file_bytes)

    asset = Asset(
        project_id=project_id,
        kind=kind,
        path=relative_path,
        sha256=sha256,
        mime=mime,
        size_bytes=len(file_bytes),
    )
    session.add(asset)
    await session.flush()
    await session.refresh(asset)

    if bom_drafts is not None:
        # REPLACE strategy — drop all previous bom_items for this project,
        # then bulk-insert the new drafts. Same DB transaction as the asset
        # insert so either both land or neither does.
        await session.execute(
            delete(BomItem).where(BomItem.project_id == project_id)
        )
        session.add_all(
            [
                BomItem(
                    project_id=project_id,
                    designator=d.designator,
                    value=d.value,
                    package=d.package,
                    qty=d.qty,
                    extra=d.extra,
                    mi_likely=d.mi_likely,
                    component_type=d.component_type,
                )
                for d in bom_drafts
            ]
        )
        await session.flush()

    return asset, True


async def list_assets(session: AsyncSession, project_id: uuid.UUID) -> list[Asset]:
    result = await session.execute(
        select(Asset).where(Asset.project_id == project_id).order_by(Asset.uploaded_at.desc())
    )
    return list(result.scalars().all())


async def get_asset(
    session: AsyncSession, project_id: uuid.UUID, asset_id: uuid.UUID
) -> Asset:
    asset = (
        await session.execute(
            select(Asset).where(Asset.id == asset_id, Asset.project_id == project_id)
        )
    ).scalar_one_or_none()
    if asset is None:
        raise AssetNotFoundError(str(asset_id))
    return asset


def absolute_path(asset: Asset) -> Path:
    config = get_config()
    return Path(config.storage_root) / asset.path
