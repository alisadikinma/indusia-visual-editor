"""V-1 (editor): GET /api/projects/{id}/training/split-status proxy.

Resolves the service model name from the latest AdaptRun.model_dir basename and
proxies to auto-inspect-service via the injected TrainingClient (no hardcoded
port). DB-gated, like the sibling training-route tests.
"""

from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from indusia_visual_editor.db.models import AdaptRun
from indusia_visual_editor.main import app
from indusia_visual_editor.routes.training import (
    reset_training_client_factory,
    set_training_client_factory,
)
from indusia_visual_editor.services.inspect_service.exceptions import (
    InspectServiceConnectionError,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("IVE_DATABASE_URL"),
    reason="IVE_DATABASE_URL not set; start docker-compose.dev.yml postgres first.",
)


class _FakeSplitClient:
    raise_on_call: Exception | None = None
    last_model_name: str | None = None
    payload: dict = {
        "model_name": "abc",
        "seed": 7,
        "test_pct": 15,
        "min_test_per_class": 25,
        "per_component": [
            {
                "component": "R1",
                "train_count": 8,
                "test_count": 30,
                "per_class_test_counts": {"good": 3, "ng": 27},
                "unstable": False,
                "unstable_classes": [],
            }
        ],
    }

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self.base_url = base_url
        self.timeout = timeout

    async def get_split_status(self, model_name: str) -> dict:
        type(self).last_model_name = model_name
        if type(self).raise_on_call is not None:
            raise type(self).raise_on_call
        return type(self).payload

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
def fake_split_client():
    _FakeSplitClient.raise_on_call = None
    _FakeSplitClient.last_model_name = None
    set_training_client_factory(_FakeSplitClient)
    yield
    reset_training_client_factory()


async def _create_project(client: AsyncClient, suffix: str) -> uuid.UUID:
    # Unique slug per run — the dev DB persists across runs (no rollback fixture).
    uniq = f"{suffix}-{uuid.uuid4().hex[:8]}"
    resp = await client.post(
        "/api/projects",
        json={"name": f"Split {uniq}", "slug": f"split-{uniq}"},
    )
    assert resp.status_code in (200, 201), resp.text
    return uuid.UUID(resp.json()["data"]["id"])


async def _seed_adapt_run(session, project_id, model_dir):
    adapt = AdaptRun(
        id=uuid.uuid4(),
        project_id=project_id,
        pcb_name="pcb",
        model_dir=model_dir,
        inspected_count=1,
        status="ok",
    )
    session.add(adapt)
    await session.commit()
    return adapt


@pytest.mark.asyncio
async def test_split_status_proxies_with_basename_model_name(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _create_project(client, "ok")
    # Windows-style path → basename must still resolve to the model name.
    await _seed_adapt_run(query_session, pid, model_dir=r"D:\srv\models\pcb_1")

    resp = await client.get(f"/api/projects/{pid}/training/split-status")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] is True
    assert body["data"]["seed"] == 7
    assert body["data"]["per_component"][0]["component"] == "R1"
    # Service was asked for the basename of model_dir.
    assert _FakeSplitClient.last_model_name == "pcb_1"


@pytest.mark.asyncio
async def test_split_status_null_when_no_adapt_run(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _create_project(client, "noadapt")
    resp = await client.get(f"/api/projects/{pid}/training/split-status")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] is True
    assert body["data"] is None


@pytest.mark.asyncio
async def test_split_status_502_on_service_error(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _create_project(client, "boom")
    await _seed_adapt_run(query_session, pid, model_dir="/srv/models/x")
    _FakeSplitClient.raise_on_call = InspectServiceConnectionError("down")

    resp = await client.get(f"/api/projects/{pid}/training/split-status")
    assert resp.status_code == 502, resp.text
