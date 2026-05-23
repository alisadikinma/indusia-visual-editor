"""Phase 7.4 — GET /api/training/{run_id}/stream SSE relay.

The relay opens an SSE stream against the sibling auto-inspect-service via
the test-injected `TrainingClient` fake, propagates each `data:` event into
our own EventSourceResponse, and persists status + metrics transitions on
the underlying TrainRun row.
"""

from __future__ import annotations

import os
import uuid
from typing import AsyncIterator

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
)


pytestmark = pytest.mark.skipif(
    not os.environ.get("IVE_DATABASE_URL"),
    reason="IVE_DATABASE_URL not set; start docker-compose.dev.yml postgres first.",
)


class _ScriptedTrainingClient:
    """Fake that emits a configurable event sequence from `events_to_yield`
    and accepts a start_training call that returns `job_id`."""

    events_to_yield: list[dict] = []
    raise_on_stream: Exception | None = None
    job_id: str = "job-stream-001"

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self.base_url = base_url
        self.timeout = timeout

    async def start_training(self, *, model_dir: str) -> str:
        return type(self).job_id

    async def stream_progress(self, job_id: str) -> AsyncIterator[dict]:
        if type(self).raise_on_stream is not None:
            raise type(self).raise_on_stream
        for event in type(self).events_to_yield:
            yield event

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
    _ScriptedTrainingClient.events_to_yield = []
    _ScriptedTrainingClient.raise_on_stream = None
    _ScriptedTrainingClient.job_id = "job-stream-001"
    set_training_client_factory(_ScriptedTrainingClient)
    yield
    reset_training_client_factory()


@pytest.fixture(autouse=True)
def reset_sse_starlette_appstatus():
    """sse-starlette stashes a module-level `should_exit_event` (an
    `anyio.Event`) on first request — but the event is bound to the
    event loop that created it. Across tests, pytest-asyncio swaps event
    loops, so the stale event from the previous test would either hang
    or raise inside `AppStatus.should_exit_event.wait()`. Resetting the
    flags before each test gives each invocation a clean slate."""
    from sse_starlette.sse import AppStatus

    AppStatus.should_exit = False
    AppStatus.should_exit_event = None
    yield
    AppStatus.should_exit = False
    AppStatus.should_exit_event = None


async def _create_project(client: AsyncClient, suffix: str) -> uuid.UUID:
    slug = f"stream-{suffix}-{uuid.uuid4().hex[:8]}"
    r = await client.post("/api/projects", json={"name": slug, "slug": slug})
    assert r.status_code == 201
    return uuid.UUID(r.json()["data"]["id"])


async def _start_run(
    client: AsyncClient,
    query_session: AsyncSession,
    suffix: str,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Returns (project_id, run_id) — creates project + adapt_run + posts start."""
    pid = await _create_project(client, suffix)
    adapt = AdaptRun(
        project_id=pid,
        pcb_name="x",
        model_dir="/srv/models/x",
        inspected_count=1,
        status="ok",
    )
    query_session.add(adapt)
    await query_session.commit()

    r = await client.post(f"/api/projects/{pid}/training/start")
    assert r.status_code == 201, r.text
    run_id = uuid.UUID(r.json()["data"]["id"])
    return pid, run_id


@pytest.mark.asyncio
async def test_get_training_stream_relays_events_and_persists_terminal(
    client: AsyncClient, query_session: AsyncSession
):
    """A 3-event sequence (running → epoch → succeeded) lands as SSE on the
    wire and updates the TrainRun row to status='succeeded' + metrics_json."""

    _ScriptedTrainingClient.events_to_yield = [
        {"event": "running", "epoch": 0},
        {"event": "epoch", "epoch": 5, "loss": 0.32},
        {
            "event": "succeeded",
            "metrics": {"mAP": 0.91, "per_component_f1": {"R1": 0.95, "C4": 0.88}},
        },
    ]

    _pid, run_id = await _start_run(client, query_session, "happy")

    r = await client.get(f"/api/training/{run_id}/stream")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/event-stream")
    body = r.text

    # All three event JSON payloads appear in the body (sse-starlette
    # serialises each `data:` line; we don't depend on exact framing,
    # just the presence of the payload's distinctive substrings).
    assert '"event": "running"' in body or '"event":"running"' in body
    assert "0.32" in body
    assert "0.91" in body
    assert "per_component_f1" in body

    # Terminal state persisted on the row.
    row = (
        await query_session.execute(
            select(TrainRun).where(TrainRun.id == run_id)
        )
    ).scalar_one()
    assert row.status == "succeeded"
    assert row.metrics_json is not None
    assert row.metrics_json["mAP"] == 0.91
    assert row.metrics_json["per_component_f1"]["R1"] == 0.95
    assert row.ended_at is not None


@pytest.mark.asyncio
async def test_get_training_stream_persists_failed_status(
    client: AsyncClient, query_session: AsyncSession
):
    _ScriptedTrainingClient.events_to_yield = [
        {"event": "running"},
        {"event": "failed", "error": "CUDA OOM"},
    ]
    _pid, run_id = await _start_run(client, query_session, "failed")

    r = await client.get(f"/api/training/{run_id}/stream")
    assert r.status_code == 200

    row = (
        await query_session.execute(
            select(TrainRun).where(TrainRun.id == run_id)
        )
    ).scalar_one()
    assert row.status == "failed"
    assert row.error_text is not None
    assert "CUDA OOM" in row.error_text
    assert row.ended_at is not None


@pytest.mark.asyncio
async def test_get_training_stream_running_intermediate_persists(
    client: AsyncClient, query_session: AsyncSession
):
    """If the stream emits a `running` event without a terminal, status moves
    from pending → running. The connection eventually closing without a
    terminal leaves the row in `running` — operator can re-attach later."""
    _ScriptedTrainingClient.events_to_yield = [
        {"event": "running", "epoch": 1},
        {"event": "epoch", "epoch": 2, "loss": 0.5},
    ]
    _pid, run_id = await _start_run(client, query_session, "running")

    r = await client.get(f"/api/training/{run_id}/stream")
    assert r.status_code == 200

    row = (
        await query_session.execute(
            select(TrainRun).where(TrainRun.id == run_id)
        )
    ).scalar_one()
    assert row.status == "running"
    assert row.ended_at is None
    assert row.metrics_json is None


@pytest.mark.asyncio
async def test_get_training_stream_404_for_unknown_run(client: AsyncClient):
    bogus = uuid.uuid4()
    r = await client.get(f"/api/training/{bogus}/stream")
    assert r.status_code == 404
    assert r.json()["status"] is False


@pytest.mark.asyncio
async def test_get_training_stream_marks_failed_on_service_connection_error(
    client: AsyncClient, query_session: AsyncSession
):
    """If the relay can't open the stream against the service, mark the row
    as failed and surface the error text — the operator must see why."""
    _ScriptedTrainingClient.raise_on_stream = InspectServiceConnectionError(
        "service refused"
    )
    _pid, run_id = await _start_run(client, query_session, "svc-down")

    r = await client.get(f"/api/training/{run_id}/stream")
    # SSE endpoint still returns 200 — the failure is reported inside
    # the stream body AND persisted on the row.
    assert r.status_code == 200
    body = r.text
    assert "error" in body.lower()

    row = (
        await query_session.execute(
            select(TrainRun).where(TrainRun.id == run_id)
        )
    ).scalar_one()
    assert row.status == "failed"
    assert row.error_text is not None
    assert "service refused" in row.error_text
