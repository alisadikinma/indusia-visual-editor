"""Phase 10.3 — POST /api/projects/{id}/deploy route + deployments row.

Tests use a fake `push_model` injected via `set_push_model_callable`
(mirrors training_client / llm_client factory seams) so we never spawn
a real `ais` subprocess in CI.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from indusia_visual_editor.db.models import AdaptRun, Deployment, TrainRun
from indusia_visual_editor.main import app
from indusia_visual_editor.routes.deploy import (
    reset_notify_edges_callable,
    reset_push_model_callable,
    set_notify_edges_callable,
    set_push_model_callable,
)
from indusia_visual_editor.services.deploy.registry import PushResult
from indusia_visual_editor.services.edge.notify import NotifyOutcome


pytestmark = pytest.mark.skipif(
    not os.environ.get("IVE_DATABASE_URL"),
    reason="IVE_DATABASE_URL not set; start docker-compose.dev.yml postgres first.",
)


_PUSH_OK = PushResult(
    ok=True,
    stage="done",
    returncode=0,
    stdout="ok\n",
    stderr="",
)


_PUSH_FAIL = PushResult(
    ok=False,
    stage="push",
    returncode=1,
    stdout="",
    stderr="Push failed: connection refused\n",
)


class _PushRecorder:
    """Captures the kwargs each `push_model` call gets, returns scripted result."""

    def __init__(self, result: PushResult) -> None:
        self.result = result
        self.calls: list[dict] = []

    async def __call__(self, **kwargs) -> PushResult:
        self.calls.append(kwargs)
        return self.result


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def isolated_storage_root(tmp_path, monkeypatch):
    monkeypatch.setenv("IVE_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("IVE_REGISTRY_ROOT", str(tmp_path / "registry"))


@pytest.fixture
async def query_session():
    engine = create_async_engine(os.environ["IVE_DATABASE_URL"], future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.fixture(autouse=True)
def reset_push():
    yield
    reset_push_model_callable()


class _NotifyRecorder:
    """Captures notify_edges invocations + returns scripted outcomes."""

    def __init__(self, outcomes: list[NotifyOutcome] | None = None) -> None:
        self.outcomes = outcomes or []
        self.calls: list[dict] = []

    async def __call__(self, **kwargs) -> list[NotifyOutcome]:
        self.calls.append(kwargs)
        return self.outcomes


@pytest.fixture(autouse=True)
def stub_notify():
    """Default: notify returns [] so M10 tests stay green without edge seeds.
    Tests that care about the edges_notified path override this in-body."""
    set_notify_edges_callable(_NotifyRecorder([]))
    yield
    reset_notify_edges_callable()


async def _create_project(client: AsyncClient, suffix: str) -> tuple[uuid.UUID, str]:
    slug = f"deploy-{suffix}-{uuid.uuid4().hex[:8]}"
    r = await client.post("/api/projects", json={"name": slug, "slug": slug})
    assert r.status_code == 201
    body = r.json()["data"]
    return uuid.UUID(body["id"]), body["slug"]


async def _seed_succeeded_train_run(
    session: AsyncSession,
    project_id: uuid.UUID,
    *,
    metrics: dict | None = None,
) -> TrainRun:
    adapt = AdaptRun(
        project_id=project_id,
        pcb_name="dep-board",
        model_dir="/srv/models/dep",
        inspected_count=1,
        status="ok",
    )
    session.add(adapt)
    await session.commit()
    run = TrainRun(
        project_id=project_id,
        adapt_run_id=adapt.id,
        service_job_id="job-dep",
        status="succeeded",
        metrics_json=metrics or {"mAP": 0.9},
        ended_at=datetime.now(timezone.utc),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


@pytest.mark.asyncio
async def test_post_deploy_succeeds_and_persists_row(
    client: AsyncClient, query_session: AsyncSession
):
    pid, slug = await _create_project(client, "happy")
    run = await _seed_succeeded_train_run(query_session, pid)

    rec = _PushRecorder(_PUSH_OK)
    set_push_model_callable(rec)

    r = await client.post(f"/api/projects/{pid}/deploy")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] is True
    data = body["data"]
    assert data["project_id"] == str(pid)
    assert data["train_run_id"] == str(run.id)
    assert data["status"] == "succeeded"
    assert data["model_version"]  # non-empty
    assert data["error_text"] is None

    # push_model was called with the project slug as pcb_name.
    assert len(rec.calls) == 1
    assert rec.calls[0]["pcb_name"] == slug

    row = (
        await query_session.execute(
            select(Deployment).where(Deployment.project_id == pid)
        )
    ).scalar_one()
    assert row.status == "succeeded"
    assert row.train_run_id == run.id


@pytest.mark.asyncio
async def test_post_deploy_records_failed_status_when_push_fails(
    client: AsyncClient, query_session: AsyncSession
):
    pid, _ = await _create_project(client, "pushfail")
    await _seed_succeeded_train_run(query_session, pid)

    set_push_model_callable(_PushRecorder(_PUSH_FAIL))

    r = await client.post(f"/api/projects/{pid}/deploy")
    assert r.status_code == 502, r.text
    body = r.json()
    assert body["status"] is False

    # Row IS persisted even on failure — the audit trail matters more
    # than a clean DB. Status='failed' + error_text captures the stage.
    row = (
        await query_session.execute(
            select(Deployment).where(Deployment.project_id == pid)
        )
    ).scalar_one()
    assert row.status == "failed"
    assert row.error_text is not None
    assert "connection refused" in row.error_text


@pytest.mark.asyncio
async def test_post_deploy_422_when_no_succeeded_train_run(
    client: AsyncClient, query_session: AsyncSession
):
    pid, _ = await _create_project(client, "no-run")

    # Seed a non-succeeded run instead — must NOT be selected.
    adapt = AdaptRun(
        project_id=pid,
        pcb_name="x",
        model_dir="/srv/models/x",
        inspected_count=1,
        status="ok",
    )
    query_session.add(adapt)
    await query_session.commit()
    query_session.add(
        TrainRun(
            project_id=pid,
            adapt_run_id=adapt.id,
            service_job_id="job-running",
            status="running",
        )
    )
    await query_session.commit()

    r = await client.post(f"/api/projects/{pid}/deploy")
    assert r.status_code == 422, r.text
    assert r.json()["status"] is False

    # No row leaked.
    rows = (
        await query_session.execute(
            select(Deployment).where(Deployment.project_id == pid)
        )
    ).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_post_deploy_404_for_unknown_project(client: AsyncClient):
    bogus = uuid.uuid4()
    r = await client.post(f"/api/projects/{bogus}/deploy")
    assert r.status_code == 404
    assert r.json()["status"] is False


@pytest.mark.asyncio
async def test_post_deploy_picks_latest_succeeded_train_run(
    client: AsyncClient, query_session: AsyncSession
):
    """Multiple succeeded runs — deploy uses the most recent (ended_at desc),
    matching the M9 eval comparison ordering."""
    pid, _ = await _create_project(client, "latest")

    adapt = AdaptRun(
        project_id=pid,
        pcb_name="x",
        model_dir="/srv/models/x",
        inspected_count=1,
        status="ok",
    )
    query_session.add(adapt)
    await query_session.commit()

    old = TrainRun(
        project_id=pid,
        adapt_run_id=adapt.id,
        service_job_id="job-old",
        status="succeeded",
        metrics_json={"mAP": 0.7},
        ended_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    new = TrainRun(
        project_id=pid,
        adapt_run_id=adapt.id,
        service_job_id="job-new",
        status="succeeded",
        metrics_json={"mAP": 0.9},
        ended_at=datetime(2026, 5, 23, tzinfo=timezone.utc),
    )
    query_session.add_all([old, new])
    await query_session.commit()

    set_push_model_callable(_PushRecorder(_PUSH_OK))

    r = await client.post(f"/api/projects/{pid}/deploy")
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["train_run_id"] == str(new.id)


@pytest.mark.asyncio
async def test_get_deploy_history_lists_deployments_for_project(
    client: AsyncClient, query_session: AsyncSession
):
    pid, _ = await _create_project(client, "hist")
    await _seed_succeeded_train_run(query_session, pid)

    set_push_model_callable(_PushRecorder(_PUSH_OK))

    r1 = await client.post(f"/api/projects/{pid}/deploy")
    assert r1.status_code == 201
    r2 = await client.post(f"/api/projects/{pid}/deploy")
    assert r2.status_code == 201

    r = await client.get(f"/api/projects/{pid}/deploy")
    assert r.status_code == 200, r.text
    rows = r.json()["data"]
    assert isinstance(rows, list)
    assert len(rows) == 2


# ---------------- Phase 11.2 — notify integration ----------------


@pytest.mark.asyncio
async def test_post_deploy_persists_edges_notified_jsonb_on_success(
    client: AsyncClient, query_session: AsyncSession
):
    """After a successful push, the deploy route fans out notify_edges
    and persists the per-edge outcomes into the Deployment row's
    edges_notified JSONB column."""
    pid, _ = await _create_project(client, "notify")
    await _seed_succeeded_train_run(query_session, pid)

    set_push_model_callable(_PushRecorder(_PUSH_OK))
    notify = _NotifyRecorder(
        [
            NotifyOutcome(
                edge_id="edge-a",
                name="line-a",
                ok=True,
                attempts=1,
                error=None,
            ),
            NotifyOutcome(
                edge_id="edge-b",
                name="line-b",
                ok=False,
                attempts=3,
                error="HTTP 500: down",
            ),
        ]
    )
    set_notify_edges_callable(notify)

    r = await client.post(f"/api/projects/{pid}/deploy")
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["edges_notified"] is not None
    assert set(data["edges_notified"].keys()) == {"line-a", "line-b"}
    assert data["edges_notified"]["line-a"]["ok"] is True
    assert data["edges_notified"]["line-b"]["ok"] is False
    assert data["edges_notified"]["line-b"]["attempts"] == 3

    # Notify call shape — passes deployment row + project slug.
    assert len(notify.calls) == 1
    kwargs = notify.calls[0]
    assert "deployment" in kwargs
    assert "pcb_name" in kwargs

    # DB row also reflects edges_notified.
    row = (
        await query_session.execute(
            select(Deployment).where(Deployment.project_id == pid)
        )
    ).scalar_one()
    assert row.edges_notified is not None
    assert row.edges_notified["line-a"]["ok"] is True


@pytest.mark.asyncio
async def test_post_deploy_skips_notify_on_push_failure(
    client: AsyncClient, query_session: AsyncSession
):
    """If push fails, we do NOT notify edges — they'd consume an
    incomplete deployment. CLAUDE.md §11 — edges only consume successful
    promotions."""
    pid, _ = await _create_project(client, "notify-skip")
    await _seed_succeeded_train_run(query_session, pid)

    set_push_model_callable(_PushRecorder(_PUSH_FAIL))
    notify = _NotifyRecorder([])
    set_notify_edges_callable(notify)

    r = await client.post(f"/api/projects/{pid}/deploy")
    assert r.status_code == 502
    assert len(notify.calls) == 0

    row = (
        await query_session.execute(
            select(Deployment).where(Deployment.project_id == pid)
        )
    ).scalar_one()
    assert row.edges_notified is None  # never set
    assert row.status == "failed"
