"""Bundle 2.0 — GET /api/dashboard/summary aggregation endpoint.

Read-only cross-project rollup for the redesigned DashboardView. Every number
traces to a real row: project status counts, succeeded-deployment count,
edge online/total, average of the latest succeeded-train-run mAP per project,
and per-project BOM count + latest mAP. No migration, no fabricated metrics —
trend deltas and the 7-day inspection chart are intentionally absent because
no telemetry table backs them.

Runs against the real Postgres dev container (mirrors test_dataset_stats).
"""

from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from indusia_visual_editor.db.models import BomItem, Project, TrainRun
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


@pytest.fixture
async def session():
    engine = create_async_engine(os.environ["IVE_DATABASE_URL"])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def test_summary_envelope_and_shape(client: AsyncClient):
    resp = await client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] is True
    data = body["data"]

    stats = data["stats"]
    for key in (
        "active_projects",
        "drafting",
        "training",
        "deployed",
        "failed",
        "models_deployed",
        "edges_online",
        "edges_total",
    ):
        assert isinstance(stats[key], int), key
    # avg_map is a float when at least one trained project exists, else None
    assert stats["avg_map"] is None or isinstance(stats["avg_map"], (int, float))
    assert isinstance(data["projects"], list)


async def test_summary_reflects_a_created_project(
    client: AsyncClient, session
):
    # Seed a project + 3 BOM rows + a succeeded train run with mAP directly.
    slug = f"dash-{uuid.uuid4().hex[:8]}"
    proj = Project(name="Dashboard Probe", slug=slug, status="deployed")
    session.add(proj)
    await session.flush()
    session.add_all(
        [BomItem(project_id=proj.id, designator=f"R{i}") for i in range(3)]
    )
    from indusia_visual_editor.db.models import AdaptRun

    # AdaptRun status uses its own check constraint (ok/failed); the dashboard
    # mAP rollup reads TrainRun.status, so leave AdaptRun on its default.
    adapt = AdaptRun(
        project_id=proj.id,
        pcb_name="dashboard-probe",
        model_dir="/tmp/dashboard-probe",
        inspected_count=3,
    )
    session.add(adapt)
    await session.flush()
    session.add(
        TrainRun(
            project_id=proj.id,
            adapt_run_id=adapt.id,
            service_job_id="job-dash",
            status="succeeded",
            metrics_json={"mAP": 0.84},
        )
    )
    await session.commit()

    resp = await client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    projects = resp.json()["data"]["projects"]
    row = next((p for p in projects if p["id"] == str(proj.id)), None)
    assert row is not None, "created project missing from summary"
    assert row["bom_count"] == 3
    assert row["latest_map"] == pytest.approx(0.84)
    assert row["status"] == "deployed"
