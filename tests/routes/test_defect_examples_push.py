"""V-3: POST /api/projects/{id}/defect-examples/push route (T1).

Bearer-gated proxy that resolves the service model from the latest AdaptRun and
pushes promoted defect_examples via the injected TrainingClient. DB-gated.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from indusia_visual_editor.db.models import AdaptRun, DefectExample
from indusia_visual_editor.main import app
from indusia_visual_editor.routes.training import (
    reset_training_client_factory,
    set_training_client_factory,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("IVE_DATABASE_URL"),
    reason="IVE_DATABASE_URL not set; start docker-compose.dev.yml postgres first.",
)


class _FakePush:
    pushed: list[str] = []

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        pass

    async def push_defect_example(self, model_name, *, criterion, component, source_id, image_data, bbox=None):
        type(self).pushed.append(criterion)
        honest = criterion in {"connector_pin_bending", "lifted_pin"}
        return {"track": "anomaly" if honest else "supervised", "honest_limit": honest, "written": True}

    async def aclose(self):
        pass


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def query_session():
    engine = create_async_engine(os.environ["IVE_DATABASE_URL"], future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.fixture(autouse=True)
def fake_client():
    _FakePush.pushed = []
    set_training_client_factory(_FakePush)
    yield
    reset_training_client_factory()


@pytest.fixture(autouse=True)
def storage_root(tmp_path, monkeypatch):
    # get_config() is lru_cached — clear it so the route reads the tmp storage.
    from indusia_visual_editor.config import get_config

    monkeypatch.setenv("IVE_STORAGE_ROOT", str(tmp_path))
    get_config.cache_clear()
    yield tmp_path
    get_config.cache_clear()


async def _project(client) -> uuid.UUID:
    r = await client.post("/api/projects", json={"name": f"P{uuid.uuid4().hex[:6]}", "slug": f"p-{uuid.uuid4().hex[:8]}"})
    assert r.status_code in (200, 201), r.text
    return uuid.UUID(r.json()["data"]["id"])


async def _seed(session, project_id, model_dir):
    session.add(AdaptRun(id=uuid.uuid4(), project_id=project_id, pcb_name="pcb", model_dir=model_dir, inspected_count=1, status="ok"))
    await session.commit()


@pytest.mark.asyncio
async def test_push_route_reports_and_calls_service(client, query_session, storage_root):
    pid = await _project(client)
    await _seed(query_session, pid, r"D:\srv\models\pcb_1")

    (storage_root / "c").mkdir()
    (storage_root / "c" / "a.png").write_bytes(b"\x89PNG\r\n")
    query_session.add(DefectExample(id=uuid.uuid4(), project_id=pid, defect_criterion="missing_component", roi_path="c/a.png", roi_sha256="a" * 64, designator="R1"))
    query_session.add(DefectExample(id=uuid.uuid4(), project_id=pid, defect_criterion="wrong_value", roi_path="c/a.png", roi_sha256="a" * 64, designator="U1"))
    await query_session.commit()

    resp = await client.post(f"/api/projects/{pid}/defect-examples/push")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["total"] == 2
    assert data["pushed"] == 1  # missing_component
    assert data["skipped_ocr"] == 1  # wrong_value
    assert _FakePush.pushed == ["missing_component"]


@pytest.mark.asyncio
async def test_push_route_422_without_adapt_run(client, query_session):
    pid = await _project(client)
    resp = await client.post(f"/api/projects/{pid}/defect-examples/push")
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_push_route_404_unknown_project(client):
    resp = await client.post(f"/api/projects/{uuid.uuid4()}/defect-examples/push")
    assert resp.status_code == 404
