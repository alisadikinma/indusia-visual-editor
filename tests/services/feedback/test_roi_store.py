"""ROI storage service tests (Phase C).

NON-DB — must PASS here. Uses a tmp IVE_STORAGE_ROOT so nothing touches the
real storage tree. Mirrors the sha256 dedup + size-cap semantics of
services/asset/image_store but writes ROI crops OUTSIDE the assets table.
"""

import hashlib
import uuid

import pytest

from indusia_visual_editor.config import get_config
from indusia_visual_editor.services.asset.image_store import AssetTooLargeError
from indusia_visual_editor.services.feedback.roi_store import (
    absolute_roi_path,
    save_roi,
)


@pytest.fixture(autouse=True)
def _tmp_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("IVE_STORAGE_ROOT", str(tmp_path))
    get_config.cache_clear()
    yield
    get_config.cache_clear()


def test_save_roi_writes_bytes_and_returns_path_and_sha():
    pid = uuid.uuid4()
    data = b"\xff\xd8\xff\xe0fake-jpeg-roi-bytes"
    rel_path, sha = save_roi(pid, data, "crop.jpg", mime="image/jpeg")

    assert sha == hashlib.sha256(data).hexdigest()
    assert rel_path == f"{pid}/feedback_roi/{sha}.jpg"

    abs_path = absolute_roi_path(rel_path)
    assert abs_path.exists()
    assert abs_path.read_bytes() == data


def test_save_roi_dedups_identical_bytes():
    pid = uuid.uuid4()
    data = b"identical-roi-content"
    rel1, sha1 = save_roi(pid, data, "a.png")
    rel2, sha2 = save_roi(pid, data, "b.png")
    assert rel1 == rel2
    assert sha1 == sha2
    # Only one file on disk.
    abs_path = absolute_roi_path(rel1)
    assert abs_path.exists()
    assert len(list(abs_path.parent.iterdir())) == 1


def test_save_roi_rejects_oversize():
    pid = uuid.uuid4()
    cap = get_config().max_asset_bytes
    too_big = b"x" * (cap + 1)
    with pytest.raises(AssetTooLargeError):
        save_roi(pid, too_big, "huge.jpg")
