"""Phase 5.3 — POST/GET /api/projects/{id}/llm/prelabel route + persistence."""

from __future__ import annotations

import io
import json
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from indusia_visual_editor.db.models import PreLabel
from indusia_visual_editor.main import app
from indusia_visual_editor.routes.llm import (
    reset_llm_client_factory,
    set_llm_client_factory,
)


pytestmark = pytest.mark.skipif(
    not os.environ.get("IVE_DATABASE_URL"),
    reason="IVE_DATABASE_URL not set; start docker-compose.dev.yml postgres first.",
)


PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6300010000000500010d0a2db40000000049454e44ae426082"
)


FAKE_REGIONS_JSON = json.dumps(
    {
        "regions": [
            {
                "designator": "R1",
                "bbox": [0.10, 0.20, 0.05, 0.05],
                "confidence": 0.92,
                "side": "top",
            },
            {
                "designator": "C4",
                "bbox": [0.30, 0.40, 0.06, 0.06],
                "confidence": 0.88,
                "side": "top",
            },
        ]
    }
)


class _FakeOllamaClient:
    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self.base_url = base_url
        self.timeout = timeout

    async def generate(self, **_kwargs) -> str:
        return FAKE_REGIONS_JSON

    async def chat(self, **_kwargs) -> str:
        return ""

    async def aclose(self) -> None:
        pass


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def isolated_storage_root(tmp_path, monkeypatch):
    monkeypatch.setenv("IVE_STORAGE_ROOT", str(tmp_path))


@pytest.fixture
async def query_session():
    engine = create_async_engine(os.environ["IVE_DATABASE_URL"], future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.fixture(autouse=True)
def fake_ollama():
    set_llm_client_factory(_FakeOllamaClient)
    yield
    reset_llm_client_factory()


async def _create_project(client: AsyncClient, suffix: str) -> uuid.UUID:
    slug = f"prelabel-{suffix}-{uuid.uuid4().hex[:8]}"
    r = await client.post("/api/projects", json={"name": slug, "slug": slug})
    assert r.status_code == 201
    return uuid.UUID(r.json()["data"]["id"])


async def _upload_bom(client: AsyncClient, project_id: uuid.UUID) -> None:
    csv = b"Designator,Value\nR1,10k\nC4,100uF\n"
    r = await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": "bom"},
        files={"file": ("bom.csv", io.BytesIO(csv), "text/csv")},
    )
    assert r.status_code == 201


async def _upload_golden(client: AsyncClient, project_id: uuid.UUID, side: str = "top") -> None:
    kind = f"golden_{side}"
    r = await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": kind},
        files={"file": (f"g_{side}.png", io.BytesIO(PNG_BYTES), "image/png")},
    )
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_post_prelabel_persists_regions(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _create_project(client, "happy")
    await _upload_bom(client, pid)
    await _upload_golden(client, pid, "top")

    r = await client.post(
        f"/api/projects/{pid}/llm/prelabel", params={"side": "top"}
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] is True
    assert body["data"]["side"] == "top"
    assert len(body["data"]["regions"]) == 2

    rows = (
        await query_session.execute(
            select(PreLabel).where(PreLabel.project_id == pid)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].side == "top"


@pytest.mark.asyncio
async def test_post_prelabel_422_when_no_golden_for_side(client: AsyncClient):
    pid = await _create_project(client, "nogolden")
    await _upload_bom(client, pid)
    # No golden upload at all
    r = await client.post(
        f"/api/projects/{pid}/llm/prelabel", params={"side": "top"}
    )
    assert r.status_code == 422
    assert r.json()["status"] is False
    assert "golden_top" in r.json()["message"].lower()


@pytest.mark.asyncio
async def test_post_prelabel_422_when_no_bom(client: AsyncClient):
    pid = await _create_project(client, "nobom")
    await _upload_golden(client, pid, "top")
    r = await client.post(
        f"/api/projects/{pid}/llm/prelabel", params={"side": "top"}
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_prelabel_422_invalid_side(client: AsyncClient):
    pid = await _create_project(client, "badside")
    r = await client.post(
        f"/api/projects/{pid}/llm/prelabel", params={"side": "left"}
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_prelabel_replaces_existing_for_same_side(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _create_project(client, "upsert")
    await _upload_bom(client, pid)
    await _upload_golden(client, pid, "top")

    r1 = await client.post(
        f"/api/projects/{pid}/llm/prelabel", params={"side": "top"}
    )
    assert r1.status_code == 201
    first_id = r1.json()["data"]["id"]

    r2 = await client.post(
        f"/api/projects/{pid}/llm/prelabel", params={"side": "top"}
    )
    assert r2.status_code == 201
    second_id = r2.json()["data"]["id"]
    assert second_id != first_id

    rows = (
        await query_session.execute(
            select(PreLabel).where(PreLabel.project_id == pid)
        )
    ).scalars().all()
    assert len(rows) == 1  # latest-wins, NOT duplicate


@pytest.mark.asyncio
async def test_post_prelabel_502_on_llm_validation_error(client: AsyncClient):
    class _BadClient(_FakeOllamaClient):
        async def generate(self, **_kwargs) -> str:
            return "not json at all"

    set_llm_client_factory(_BadClient)
    try:
        pid = await _create_project(client, "badjson")
        await _upload_bom(client, pid)
        await _upload_golden(client, pid, "top")

        r = await client.post(
            f"/api/projects/{pid}/llm/prelabel", params={"side": "top"}
        )
        assert r.status_code == 502
        assert r.json()["status"] is False
    finally:
        set_llm_client_factory(_FakeOllamaClient)


@pytest.mark.asyncio
async def test_get_prelabel_returns_latest_for_side(client: AsyncClient):
    pid = await _create_project(client, "get")
    await _upload_bom(client, pid)
    await _upload_golden(client, pid, "top")
    await client.post(f"/api/projects/{pid}/llm/prelabel", params={"side": "top"})

    r = await client.get(f"/api/projects/{pid}/llm/prelabel", params={"side": "top"})
    assert r.status_code == 200
    assert r.json()["data"]["side"] == "top"
    assert len(r.json()["data"]["regions"]) == 2


@pytest.mark.asyncio
async def test_get_prelabel_404_when_no_side_yet(client: AsyncClient):
    pid = await _create_project(client, "notyet")
    r = await client.get(f"/api/projects/{pid}/llm/prelabel", params={"side": "top"})
    assert r.status_code == 404
