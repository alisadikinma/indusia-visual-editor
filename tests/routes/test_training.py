"""Phase 7.3 — POST /api/projects/{id}/training/start route + train_runs persist.

Tests use a fake TrainingClient injected via `set_training_client_factory`
(mirrors the Ollama factory seam from Phase 3.4). Real auto-inspect-service
is never called from the unit suite.
"""

from __future__ import annotations

import io
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from indusia_visual_editor.db.models import AdaptRun, TrainRun
from indusia_visual_editor.main import app
from indusia_visual_editor.routes.training import (
    reset_training_client_factory,
    set_training_client_factory,
)
from indusia_visual_editor.services.inspect_service.exceptions import (
    InspectServiceConnectionError,
    InspectServiceResponseError,
    InspectServiceTimeoutError,
)


pytestmark = pytest.mark.skipif(
    not os.environ.get("IVE_DATABASE_URL"),
    reason="IVE_DATABASE_URL not set; start docker-compose.dev.yml postgres first.",
)


PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6300010000000500010d0a2db40000000049454e44ae426082"
)


class _FakeTrainingClient:
    """Drop-in replacement for `TrainingClient`. The constructor mirrors the
    real client signature so the factory swap is transparent. Behavior knobs
    live as class attributes mutated by the test fixture."""

    raise_on_start: Exception | None = None
    last_model_dir: str | None = None
    job_id: str = "job-fake-123"

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self.base_url = base_url
        self.timeout = timeout

    async def start_training(self, *, model_dir: str) -> str:
        type(self).last_model_dir = model_dir
        if type(self).raise_on_start is not None:
            raise type(self).raise_on_start
        return type(self).job_id

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
def fake_training_client():
    # Reset class-level knobs between tests so leaks don't poison neighbors.
    _FakeTrainingClient.raise_on_start = None
    _FakeTrainingClient.last_model_dir = None
    _FakeTrainingClient.job_id = "job-fake-123"
    set_training_client_factory(_FakeTrainingClient)
    yield
    reset_training_client_factory()


async def _create_project(client: AsyncClient, suffix: str) -> uuid.UUID:
    slug = f"train-{suffix}-{uuid.uuid4().hex[:8]}"
    r = await client.post("/api/projects", json={"name": slug, "slug": slug})
    assert r.status_code == 201
    return uuid.UUID(r.json()["data"]["id"])


async def _seed_adapt_run(
    session: AsyncSession, project_id: uuid.UUID, model_dir: str = "/srv/models/abc"
) -> AdaptRun:
    """Insert an AdaptRun directly — the M4 adapter route is exercised
    elsewhere; here we care only about the M7 surface."""
    adapt = AdaptRun(
        project_id=project_id,
        pcb_name="test-board",
        model_dir=model_dir,
        inspected_count=2,
        status="ok",
    )
    session.add(adapt)
    await session.commit()
    return adapt


@pytest.mark.asyncio
async def test_post_training_start_inserts_row_and_calls_service(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _create_project(client, "happy")
    adapt = await _seed_adapt_run(
        query_session, pid, model_dir="/srv/models/happy"
    )

    r = await client.post(f"/api/projects/{pid}/training/start")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] is True
    data = body["data"]
    assert data["project_id"] == str(pid)
    assert data["adapt_run_id"] == str(adapt.id)
    assert data["service_job_id"] == "job-fake-123"
    assert data["status"] == "pending"
    assert data["started_at"] is not None
    assert data["ended_at"] is None
    assert data["metrics_json"] is None

    # Service was called with the latest adapt_run's model_dir.
    assert _FakeTrainingClient.last_model_dir == "/srv/models/happy"

    # Row persisted in DB.
    row = (
        await query_session.execute(
            select(TrainRun).where(TrainRun.project_id == pid)
        )
    ).scalar_one()
    assert row.service_job_id == "job-fake-123"
    assert row.adapt_run_id == adapt.id


@pytest.mark.asyncio
async def test_post_training_start_uses_latest_adapt_run(
    client: AsyncClient, query_session: AsyncSession
):
    """When multiple AdaptRuns exist, training picks the most recent one
    (created_at desc). The graphflow tree from the latest adapter is what
    the operator currently sees in the canvas, so it's what we train."""
    pid = await _create_project(client, "latest-adapt")
    await _seed_adapt_run(query_session, pid, model_dir="/srv/models/old")
    new_adapt = await _seed_adapt_run(query_session, pid, model_dir="/srv/models/new")

    r = await client.post(f"/api/projects/{pid}/training/start")
    assert r.status_code == 201, r.text
    assert _FakeTrainingClient.last_model_dir == "/srv/models/new"
    assert r.json()["data"]["adapt_run_id"] == str(new_adapt.id)


@pytest.mark.asyncio
async def test_post_training_start_422_when_no_adapt_run(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _create_project(client, "no-adapt")
    r = await client.post(f"/api/projects/{pid}/training/start")
    assert r.status_code == 422, r.text
    assert r.json()["status"] is False
    # No row leaked.
    rows = (
        await query_session.execute(
            select(TrainRun).where(TrainRun.project_id == pid)
        )
    ).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_post_training_start_502_on_connection_error_leaves_no_row(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _create_project(client, "conn-err")
    await _seed_adapt_run(query_session, pid, model_dir="/srv/models/x")

    _FakeTrainingClient.raise_on_start = InspectServiceConnectionError("refused")

    r = await client.post(f"/api/projects/{pid}/training/start")
    assert r.status_code == 502, r.text
    assert r.json()["status"] is False

    rows = (
        await query_session.execute(
            select(TrainRun).where(TrainRun.project_id == pid)
        )
    ).scalars().all()
    assert rows == [], "no TrainRun row should be persisted on service failure"


@pytest.mark.asyncio
async def test_post_training_start_502_on_timeout(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _create_project(client, "timeout")
    await _seed_adapt_run(query_session, pid, model_dir="/srv/models/x")

    _FakeTrainingClient.raise_on_start = InspectServiceTimeoutError("slow")

    r = await client.post(f"/api/projects/{pid}/training/start")
    assert r.status_code == 502
    assert r.json()["status"] is False


@pytest.mark.asyncio
async def test_post_training_start_502_on_bad_response(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _create_project(client, "bad-resp")
    await _seed_adapt_run(query_session, pid, model_dir="/srv/models/x")

    _FakeTrainingClient.raise_on_start = InspectServiceResponseError(
        "missing job_id"
    )

    r = await client.post(f"/api/projects/{pid}/training/start")
    assert r.status_code == 502
    assert r.json()["status"] is False


@pytest.mark.asyncio
async def test_get_training_lists_runs_for_project(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _create_project(client, "list")
    await _seed_adapt_run(query_session, pid, model_dir="/srv/models/x")

    # Two POSTs → two rows.
    r1 = await client.post(f"/api/projects/{pid}/training/start")
    assert r1.status_code == 201
    _FakeTrainingClient.job_id = "job-fake-456"
    r2 = await client.post(f"/api/projects/{pid}/training/start")
    assert r2.status_code == 201

    r = await client.get(f"/api/projects/{pid}/training")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] is True
    runs = body["data"]
    assert isinstance(runs, list)
    assert len(runs) == 2
    job_ids = {run["service_job_id"] for run in runs}
    assert job_ids == {"job-fake-123", "job-fake-456"}


@pytest.mark.asyncio
async def test_get_training_returns_empty_list_for_project_with_no_runs(
    client: AsyncClient,
):
    pid = await _create_project(client, "empty")
    r = await client.get(f"/api/projects/{pid}/training")
    assert r.status_code == 200
    assert r.json()["data"] == []


@pytest.mark.asyncio
async def test_post_training_start_404_for_unknown_project(client: AsyncClient):
    bogus = uuid.uuid4()
    r = await client.post(f"/api/projects/{bogus}/training/start")
    assert r.status_code == 404
    assert r.json()["status"] is False
