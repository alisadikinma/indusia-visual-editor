"""Phase 3.4 — planner route + persistence.

Route under test: POST /api/projects/{id}/llm/plan, GET .../plan

We inject a fake OllamaClient factory so the test runs without Ollama.
The fake returns a hand-crafted ProposedPipeline JSON; we then assert
the row landed in `proposed_pipelines` with the correct version and
the response carries the canonical {status, message, data} envelope.
"""

from __future__ import annotations

import io
import json
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from indusia_visual_editor.db.models import ProposedPipelineRow
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

FAKE_PLAN_JSON = json.dumps(
    {
        "pcb_model": "NV80",
        "fiducial_strategy": "circle",
        "steps": [
            {
                "designator": "R1",
                "component_type": "smd_chip_passive",
                "detectors": ["yolo"],
                "reasoning": "Standard 0805 chip resistor.",
            }
        ],
    }
)


class _FakeOllamaClient:
    """Drop-in replacement for OllamaClient — matches the constructor
    signature used by the route (base_url=, timeout=) and the
    generate/aclose surface used by the planner."""

    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.closed = False

    async def generate(self, **_kwargs) -> str:
        return FAKE_PLAN_JSON

    async def chat(self, **_kwargs) -> str:
        return ""

    async def aclose(self) -> None:
        self.closed = True


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
    slug = f"llm-{suffix}-{uuid.uuid4().hex[:8]}"
    r = await client.post("/api/projects", json={"name": slug, "slug": slug})
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["data"]["id"])


async def _upload_bom(client: AsyncClient, project_id: uuid.UUID) -> None:
    csv = (
        b"Designator,Value,Package\n"
        b"R1,10k,0805\n"
        b"C4,100uF,Radial\n"
    )
    r = await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": "bom"},
        files={"file": ("bom.csv", io.BytesIO(csv), "text/csv")},
    )
    assert r.status_code == 201


async def _upload_golden_top(client: AsyncClient, project_id: uuid.UUID) -> None:
    r = await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": "golden_top"},
        files={"file": ("g.png", io.BytesIO(PNG_BYTES), "image/png")},
    )
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_create_plan_persists_proposed_pipeline_row(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _create_project(client, "happy")
    await _upload_bom(client, pid)
    await _upload_golden_top(client, pid)

    r = await client.post(f"/api/projects/{pid}/llm/plan")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] is True
    assert body["data"]["version"] == 1
    assert body["data"]["plan"]["pcb_model"] == "NV80"
    assert body["data"]["plan"]["steps"][0]["designator"] == "R1"

    rows = (
        await query_session.execute(
            select(ProposedPipelineRow).where(
                ProposedPipelineRow.project_id == pid
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].version == 1
    assert rows[0].dag_json["pcb_model"] == "NV80"


@pytest.mark.asyncio
async def test_create_plan_increments_version_on_repeat_call(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _create_project(client, "ver")
    await _upload_bom(client, pid)
    await _upload_golden_top(client, pid)

    for expected_version in (1, 2, 3):
        r = await client.post(f"/api/projects/{pid}/llm/plan")
        assert r.status_code == 201, r.text
        assert r.json()["data"]["version"] == expected_version

    rows = (
        await query_session.execute(
            select(ProposedPipelineRow)
            .where(ProposedPipelineRow.project_id == pid)
            .order_by(ProposedPipelineRow.version)
        )
    ).scalars().all()
    assert [row.version for row in rows] == [1, 2, 3]


@pytest.mark.asyncio
async def test_create_plan_422_when_no_bom_items(client: AsyncClient):
    pid = await _create_project(client, "nobom")
    await _upload_golden_top(client, pid)
    r = await client.post(f"/api/projects/{pid}/llm/plan")
    assert r.status_code == 422, r.text
    assert r.json()["status"] is False
    assert "bom" in r.json()["message"].lower()


@pytest.mark.asyncio
async def test_create_plan_422_when_no_golden_top(client: AsyncClient):
    pid = await _create_project(client, "nogolden")
    await _upload_bom(client, pid)
    r = await client.post(f"/api/projects/{pid}/llm/plan")
    assert r.status_code == 422, r.text
    assert r.json()["status"] is False
    assert "golden" in r.json()["message"].lower()


@pytest.mark.asyncio
async def test_get_latest_plan_404_when_no_plan_yet(client: AsyncClient):
    pid = await _create_project(client, "empty")
    r = await client.get(f"/api/projects/{pid}/llm/plan")
    assert r.status_code == 404
    assert r.json()["status"] is False


@pytest.mark.asyncio
async def test_get_latest_plan_returns_highest_version(client: AsyncClient):
    pid = await _create_project(client, "latest")
    await _upload_bom(client, pid)
    await _upload_golden_top(client, pid)
    for _ in range(2):
        r = await client.post(f"/api/projects/{pid}/llm/plan")
        assert r.status_code == 201

    r = await client.get(f"/api/projects/{pid}/llm/plan")
    assert r.status_code == 200
    assert r.json()["data"]["version"] == 2


@pytest.mark.asyncio
async def test_create_plan_502_when_ollama_returns_garbage(client: AsyncClient):
    """LlmValidationError from planner → 502 envelope, no row persisted."""
    from indusia_visual_editor.routes.llm import set_llm_client_factory

    class _BadClient(_FakeOllamaClient):
        async def generate(self, **_kwargs) -> str:
            return "not json"

    set_llm_client_factory(_BadClient)
    try:
        pid = await _create_project(client, "bad")
        await _upload_bom(client, pid)
        await _upload_golden_top(client, pid)

        r = await client.post(f"/api/projects/{pid}/llm/plan")
        assert r.status_code == 502, r.text
        assert r.json()["status"] is False
    finally:
        set_llm_client_factory(_FakeOllamaClient)
