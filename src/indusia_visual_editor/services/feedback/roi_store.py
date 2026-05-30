"""Filesystem ROI-crop storage for the inspection-feedback loop.

ROI crops live under `<IVE_STORAGE_ROOT>/{project_id}/feedback_roi/{sha256}{ext}`
— OUTSIDE the `assets` table. They are runtime evidence attached to an
`inspection_feedback` row, not project assets, so they get their own kind
directory and are never surfaced by the assets routes.

The on-disk filename is derived entirely from the SHA256 (path traversal via
the caller-provided filename is impossible — only the extension is read from
it). Dedup is per (project_id, sha256): writing identical bytes twice returns
the same relative path and never duplicates the file. The size cap and
extension logic mirror services/asset/image_store so the two storage paths
stay behaviourally consistent.
"""

import hashlib
import uuid
from pathlib import Path

from indusia_visual_editor.config import get_config
from indusia_visual_editor.services.asset.image_store import (
    AssetTooLargeError,
    _safe_extension,
)


def save_roi(
    project_id: uuid.UUID,
    file_bytes: bytes,
    filename: str,
    mime: str | None = None,
) -> tuple[str, str]:
    """Persist an ROI crop and return (relative_path, sha256).

    Raises AssetTooLargeError when the bytes exceed IVE_MAX_ASSET_BYTES.
    Identical bytes dedup to the existing file (idempotent write).
    """
    config = get_config()
    if len(file_bytes) > config.max_asset_bytes:
        raise AssetTooLargeError(
            f"{len(file_bytes)} bytes exceeds limit {config.max_asset_bytes}"
        )

    sha256 = hashlib.sha256(file_bytes).hexdigest()
    ext = _safe_extension(filename, mime)
    relative_path = f"{project_id}/feedback_roi/{sha256}{ext}"

    target_dir = Path(config.storage_root) / str(project_id) / "feedback_roi"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / f"{sha256}{ext}"

    # Dedup: identical bytes already on disk → skip the write.
    if not target_file.exists():
        target_file.write_bytes(file_bytes)

    return relative_path, sha256


def absolute_roi_path(relative_path: str) -> Path:
    """Resolve an ROI relative path against IVE_STORAGE_ROOT."""
    config = get_config()
    return Path(config.storage_root) / relative_path
