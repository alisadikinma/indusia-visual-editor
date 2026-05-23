"""Phase 9.1 — GET /api/training/{run_id}/eval route.

Returns combined `{metrics, predictions, prev_metrics}` for a completed
TrainRun. Metrics come from `train_runs.metrics_json` (already persisted by
the M7 SSE relay on the terminal `succeeded` event). Sample predictions are
fetched from `auto-inspect-service` via `TrainingClient.get_predictions`.
`prev_metrics` is the second-most-recent succeeded TrainRun's metrics for
the same project, or `None` if this is the first successful run.

Tests use a fake `TrainingClient` injected via the shared
`set_training_client_factory` seam (same pattern as test_training.py).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
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
)


pytestmark = pytest.mark.skipif(
    not os.environ.get("IVE_DATABASE_URL"),
    reason="IVE_DATABASE_URL not set; start docker-compose.dev.yml postgres first.",
)


_SAMPLE_PREDICTIONS: list[dict] = [
    {
        "designator": "C4",
        "bbox": [0.10, 0.20, 0.05, 0.07],
        "verdict": "fail",
        "is_false_positive": True,
        "is_false_negative": False,
        "score": 0.91,
    },
    {
        "designator": "R7",
        "bbox": [0.45, 0.55, 0.04, 0.04],
        "verdict": "pass",
        "is_false_positive": False,
        "is_false_negative": True,
        "score": 0.32,
    },
]


class _FakeTrainingClient:
    """Drop-in replacement for `TrainingClient`. Only the eval surface is
    exercised here — `start_training` / `stream_progress` are inert."""

    raise_on_predictions: Exception | None = None
    last_job_id: str | None = None
    predictions: list[dict] = list(_SAMPLE_PREDICTIONS)

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self.base_url = base_url
        self.timeout = timeout

    async def start_training(self, *, model_dir: str) -> str:  # pragma: no cover
        return "unused"

    async def get_predictions(self, job_id: str) -> list[dict]:
        type(self).last_job_id = job_id
        if type(self).raise_on_predictions is not None:
            raise type(self).raise_on_predictions
        return list(type(self).predictions)

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
    _FakeTrainingClient.raise_on_predictions = None
    _FakeTrainingClient.last_job_id = None
    _FakeTrainingClient.predictions = list(_SAMPLE_PREDICTIONS)
    set_training_client_factory(_FakeTrainingClient)
    yield
    reset_training_client_factory()


async def _create_project(client: AsyncClient, suffix: str) -> uuid.UUID:
    slug = f"eval-{suffix}-{uuid.uuid4().hex[:8]}"
    r = await client.post("/api/projects", json={"name": slug, "slug": slug})
    assert r.status_code == 201
    return uuid.UUID(r.json()["data"]["id"])


async def _seed_adapt_run(
    session: AsyncSession, project_id: uuid.UUID, model_dir: str = "/srv/models/x"
) -> AdaptRun:
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


async def _seed_train_run(
    session: AsyncSession,
    project_id: uuid.UUID,
    adapt_run_id: uuid.UUID,
    *,
    status: str = "succeeded",
    metrics: dict | None = None,
    service_job_id: str = "job-eval-1",
    ended_offset_sec: int = 0,
) -> TrainRun:
    run = TrainRun(
        project_id=project_id,
        adapt_run_id=adapt_run_id,
        service_job_id=service_job_id,
        status=status,
        metrics_json=metrics,
        ended_at=datetime.now(timezone.utc) if status != "pending" else None,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


@pytest.mark.asyncio
async def test_get_eval_returns_metrics_and_predictions(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _create_project(client, "happy")
    adapt = await _seed_adapt_run(query_session, pid)
    metrics = {
        "mAP": 0.87,
        "per_component_f1": {"C4": 0.92, "R7": 0.81},
    }
    run = await _seed_train_run(
        query_session, pid, adapt.id, metrics=metrics, service_job_id="job-eval-1"
    )

    r = await client.get(f"/api/training/{run.id}/eval")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] is True
    data = body["data"]
    assert data["run_id"] == str(run.id)
    assert data["metrics"] == metrics
    assert data["predictions"] == _SAMPLE_PREDICTIONS
    # No previous run — first successful train_run for the project.
    assert data["prev_metrics"] is None

    # TrainingClient was called with the run's service_job_id.
    assert _FakeTrainingClient.last_job_id == "job-eval-1"


@pytest.mark.asyncio
async def test_get_eval_includes_prev_metrics_when_second_succeeded_run(
    client: AsyncClient, query_session: AsyncSession
):
    """Comparison vs. previous succeeded run for the same project."""
    pid = await _create_project(client, "prev")
    adapt = await _seed_adapt_run(query_session, pid)

    prev_metrics = {"mAP": 0.80, "per_component_f1": {"C4": 0.85}}
    await _seed_train_run(
        query_session,
        pid,
        adapt.id,
        metrics=prev_metrics,
        service_job_id="job-eval-prev",
    )

    current_metrics = {"mAP": 0.87, "per_component_f1": {"C4": 0.92}}
    current = await _seed_train_run(
        query_session,
        pid,
        adapt.id,
        metrics=current_metrics,
        service_job_id="job-eval-cur",
    )

    r = await client.get(f"/api/training/{current.id}/eval")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["metrics"] == current_metrics
    assert data["prev_metrics"] == prev_metrics


@pytest.mark.asyncio
async def test_get_eval_404_when_run_missing(client: AsyncClient):
    bogus = uuid.uuid4()
    r = await client.get(f"/api/training/{bogus}/eval")
    assert r.status_code == 404
    assert r.json()["status"] is False


@pytest.mark.asyncio
async def test_get_eval_422_when_run_not_succeeded(
    client: AsyncClient, query_session: AsyncSession
):
    """Eval is only meaningful after the run reaches `succeeded`. A pending
    or running row has no metrics; failed runs surface error_text via the
    history endpoint instead."""
    pid = await _create_project(client, "running")
    adapt = await _seed_adapt_run(query_session, pid)
    run = await _seed_train_run(
        query_session,
        pid,
        adapt.id,
        status="running",
        metrics=None,
        service_job_id="job-running",
    )

    r = await client.get(f"/api/training/{run.id}/eval")
    assert r.status_code == 422, r.text
    assert r.json()["status"] is False


@pytest.mark.asyncio
async def test_get_eval_502_when_inspect_service_unreachable(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _create_project(client, "502")
    adapt = await _seed_adapt_run(query_session, pid)
    run = await _seed_train_run(
        query_session,
        pid,
        adapt.id,
        metrics={"mAP": 0.5},
        service_job_id="job-502",
    )

    _FakeTrainingClient.raise_on_predictions = InspectServiceConnectionError("refused")

    r = await client.get(f"/api/training/{run.id}/eval")
    assert r.status_code == 502, r.text
    assert r.json()["status"] is False


@pytest.mark.asyncio
async def test_get_eval_502_when_inspect_service_returns_bad_response(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _create_project(client, "502resp")
    adapt = await _seed_adapt_run(query_session, pid)
    run = await _seed_train_run(
        query_session,
        pid,
        adapt.id,
        metrics={"mAP": 0.5},
        service_job_id="job-502resp",
    )

    _FakeTrainingClient.raise_on_predictions = InspectServiceResponseError(
        "non-2xx"
    )

    r = await client.get(f"/api/training/{run.id}/eval")
    assert r.status_code == 502
    assert r.json()["status"] is False


@pytest.mark.asyncio
async def test_get_eval_isolates_prev_metrics_per_project(
    client: AsyncClient, query_session: AsyncSession
):
    """A succeeded run in another project must not surface as prev_metrics."""
    pid_a = await _create_project(client, "iso-a")
    pid_b = await _create_project(client, "iso-b")
    adapt_a = await _seed_adapt_run(query_session, pid_a)
    adapt_b = await _seed_adapt_run(query_session, pid_b)

    # Older successful run in project B — must NOT bleed into A's prev.
    await _seed_train_run(
        query_session,
        pid_b,
        adapt_b.id,
        metrics={"mAP": 0.99},
        service_job_id="job-bleed",
    )

    run_a = await _seed_train_run(
        query_session,
        pid_a,
        adapt_a.id,
        metrics={"mAP": 0.70},
        service_job_id="job-clean",
    )

    r = await client.get(f"/api/training/{run_a.id}/eval")
    assert r.status_code == 200
    assert r.json()["data"]["prev_metrics"] is None
