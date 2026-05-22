"""Phase 1.3 Asset upload tests.

Covers the route + service stack: multipart upload, SHA256 dedup, kind
Literal validation, 50MB size cap, path-traversal guard via sha256-named
files, list, and binary download. The dev `ive` DB at localhost:5433 is
the storage backend; files land under `tests/_storage/` per the test
config (IVE_STORAGE_ROOT) — gitignored, cleaned up by the test fixture.
"""

import io
import os
import shutil
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from indusia_visual_editor.config import get_config
from indusia_visual_editor.main import app


pytestmark = pytest.mark.skipif(
    not os.environ.get("IVE_DATABASE_URL"),
    reason="IVE_DATABASE_URL not set; start docker-compose.dev.yml postgres first.",
)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def isolated_storage_root(tmp_path, monkeypatch):
    """Each test gets its own ephemeral storage root so file IO doesn't leak."""
    monkeypatch.setenv("IVE_STORAGE_ROOT", str(tmp_path))
    get_config.cache_clear() if hasattr(get_config, "cache_clear") else None
    yield tmp_path
    shutil.rmtree(tmp_path, ignore_errors=True)


async def _create_project(client: AsyncClient, slug_suffix: str) -> str:
    slug = f"asset-{slug_suffix}-{uuid.uuid4().hex[:8]}"
    r = await client.post(
        "/api/projects", json={"name": f"Asset test {slug}", "slug": slug}
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


def _png_bytes(payload: bytes = b"fake-png-payload") -> bytes:
    return b"\x89PNG\r\n\x1a\n" + payload


@pytest.mark.asyncio
async def test_upload_golden_top_image(client: AsyncClient, isolated_storage_root: Path):
    project_id = await _create_project(client, "upload")

    response = await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": "golden_top"},
        files={"file": ("golden.png", io.BytesIO(_png_bytes()), "image/png")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] is True
    data = body["data"]
    assert data["kind"] == "golden_top"
    assert data["project_id"] == project_id
    assert len(data["sha256"]) == 64
    assert data["mime"] == "image/png"
    assert data["size_bytes"] > 0

    saved = isolated_storage_root / project_id / "golden_top"
    files = list(saved.glob("*.png"))
    assert len(files) == 1, f"expected 1 file in {saved}, got {files}"
    assert files[0].name.startswith(data["sha256"]), files[0].name


@pytest.mark.asyncio
async def test_upload_same_content_dedups(client: AsyncClient, isolated_storage_root: Path):
    project_id = await _create_project(client, "dedup")
    payload = _png_bytes(b"same-bytes")

    first = await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": "drawing"},
        files={"file": ("a.png", io.BytesIO(payload), "image/png")},
    )
    second = await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": "drawing"},
        files={"file": ("b.png", io.BytesIO(payload), "image/png")},
    )
    assert first.status_code == 201
    assert second.status_code == 200, "dedup hit should return 200 not 201"
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert first.json()["data"]["sha256"] == second.json()["data"]["sha256"]

    files = list((isolated_storage_root / project_id / "drawing").glob("*"))
    assert len(files) == 1, "dedup must not write twice"


@pytest.mark.asyncio
async def test_upload_wrong_kind_returns_422(client: AsyncClient, isolated_storage_root: Path):
    project_id = await _create_project(client, "bad-kind")
    response = await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": "schematic_pdf"},
        files={"file": ("x.png", io.BytesIO(_png_bytes()), "image/png")},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["status"] is False


@pytest.mark.asyncio
async def test_upload_oversized_returns_413(client: AsyncClient, isolated_storage_root: Path, monkeypatch):
    monkeypatch.setenv("IVE_MAX_ASSET_BYTES", "1024")  # 1 KB cap for this test
    get_config.cache_clear() if hasattr(get_config, "cache_clear") else None

    project_id = await _create_project(client, "oversize")
    big = b"X" * 2048  # 2 KB > 1 KB cap

    response = await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": "golden_top"},
        files={"file": ("big.png", io.BytesIO(big), "image/png")},
    )
    assert response.status_code == 413
    body = response.json()
    assert body["status"] is False


@pytest.mark.asyncio
async def test_upload_traversal_filename_is_safe(client: AsyncClient, isolated_storage_root: Path):
    project_id = await _create_project(client, "traversal")
    response = await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": "golden_bottom"},
        files={
            "file": (
                "../../../etc/evil.png",
                io.BytesIO(_png_bytes()),
                "image/png",
            )
        },
    )
    assert response.status_code == 201

    # No file written outside the project's storage dir.
    storage_root = Path(isolated_storage_root)
    saved = storage_root / project_id / "golden_bottom"
    files = list(saved.glob("*"))
    assert len(files) == 1

    # Sanity: nothing escaped up to siblings.
    escaped = list((storage_root / "etc").glob("**/*")) if (storage_root / "etc").exists() else []
    assert escaped == []


@pytest.mark.asyncio
async def test_list_assets_for_project(client: AsyncClient, isolated_storage_root: Path):
    project_id = await _create_project(client, "list")

    await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": "golden_top"},
        files={"file": ("g.png", io.BytesIO(_png_bytes(b"top")), "image/png")},
    )
    await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": "drawing"},
        files={"file": ("d.png", io.BytesIO(_png_bytes(b"draw")), "image/png")},
    )

    response = await client.get(f"/api/projects/{project_id}/assets")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] is True
    kinds = {a["kind"] for a in body["data"]}
    assert kinds == {"golden_top", "drawing"}


@pytest.mark.asyncio
async def test_get_asset_binary(client: AsyncClient, isolated_storage_root: Path):
    project_id = await _create_project(client, "binary")
    payload = _png_bytes(b"download-me")

    upload = await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": "golden_top"},
        files={"file": ("z.png", io.BytesIO(payload), "image/png")},
    )
    asset_id = upload.json()["data"]["id"]

    response = await client.get(f"/api/projects/{project_id}/assets/{asset_id}/binary")
    assert response.status_code == 200
    assert response.content == payload
    assert response.headers["content-type"] == "image/png"
