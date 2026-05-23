"""Phase 1.1 ORM roundtrip test: creates a Project + Asset + BomItem in the
dev Postgres, queries them back, and asserts the schema constraints land
where the design says they should.

Uses the live `ive` database in docker-compose.dev.yml — NOT a SQLite
substitute. JSONB, ENUM check constraints, and TIMESTAMPTZ behavior all
depend on Postgres specifics, so the test would mask real bugs against
SQLite.

Each test runs in its own transaction and rolls back at teardown — the dev
DB is never polluted.
"""

import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import select

from indusia_visual_editor.db.models import (
    AdaptRun,
    Asset,
    AssetKind,
    BomItem,
    Deployment,
    Edge,
    InspectScope,
    Label,
    PreLabel,
    Project,
    ProjectStatus,
    TrainRun,
)


DB_URL = os.environ.get("IVE_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DB_URL,
    reason="IVE_DATABASE_URL not set; start docker-compose.dev.yml postgres first.",
)


@pytest.fixture
async def session():
    engine = create_async_engine(DB_URL, echo=False, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
        await s.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_project_can_be_created_and_queried(session: AsyncSession):
    project = Project(
        name="NV80-017542-0501",
        slug="nv80-017542-0501",
        status=ProjectStatus.DRAFTING,
    )
    session.add(project)
    await session.flush()

    assert project.id is not None
    assert isinstance(project.id, uuid.UUID)
    assert project.created_at is not None
    assert project.created_at.tzinfo is not None, "timestamps must be timezone-aware"

    asset = Asset(
        project_id=project.id,
        kind=AssetKind.GOLDEN_TOP,
        path="nv80-017542-0501/golden_top/abc123.jpg",
        sha256="abc123" + "0" * 58,
        mime="image/jpeg",
        size_bytes=4_200_000,
    )
    session.add(asset)

    bom_item = BomItem(
        project_id=project.id,
        designator="C4",
        value="100uF/16V",
        package="Radial",
        qty=1,
        inspect_scope=InspectScope.PENDING,
        mi_likely=True,
        component_type="electrolytic_cap",
        extra={"manufacturer": "Nichicon", "tolerance": "20%"},
    )
    session.add(bom_item)
    await session.flush()

    fetched = (
        await session.execute(select(Project).where(Project.id == project.id))
    ).scalar_one()
    assert fetched.name == "NV80-017542-0501"
    assert fetched.status == ProjectStatus.DRAFTING

    fetched_asset = (
        await session.execute(select(Asset).where(Asset.project_id == project.id))
    ).scalar_one()
    assert fetched_asset.kind == AssetKind.GOLDEN_TOP
    assert fetched_asset.sha256.startswith("abc123")

    fetched_bom = (
        await session.execute(select(BomItem).where(BomItem.project_id == project.id))
    ).scalar_one()
    assert fetched_bom.designator == "C4"
    assert fetched_bom.inspect_scope == InspectScope.PENDING
    assert fetched_bom.mi_likely is True
    assert fetched_bom.extra == {"manufacturer": "Nichicon", "tolerance": "20%"}
    assert fetched_bom.defect_history_count == 0  # default


@pytest.mark.asyncio
async def test_project_slug_is_unique(session: AsyncSession):
    p1 = Project(name="Board A", slug="board-a", status=ProjectStatus.DRAFTING)
    p2 = Project(name="Board A again", slug="board-a", status=ProjectStatus.DRAFTING)
    session.add(p1)
    await session.flush()
    session.add(p2)

    with pytest.raises(Exception):  # IntegrityError on unique constraint
        await session.flush()


@pytest.mark.asyncio
async def test_bom_item_inspect_scope_defaults_to_pending(session: AsyncSession):
    project = Project(name="Default-test", slug="default-test", status=ProjectStatus.DRAFTING)
    session.add(project)
    await session.flush()

    item = BomItem(project_id=project.id, designator="R1")
    session.add(item)
    await session.flush()

    fetched = (
        await session.execute(select(BomItem).where(BomItem.id == item.id))
    ).scalar_one()
    assert fetched.inspect_scope == InspectScope.PENDING
    assert fetched.defect_history_count == 0


@pytest.mark.asyncio
async def test_pre_label_row_persists_with_side_uniqueness(session: AsyncSession):
    """Phase 5.2 — pre_labels unique on (project_id, side); latest-wins."""
    p = Project(name="prelabel-board", slug=f"prelabel-{uuid.uuid4().hex[:6]}")
    session.add(p)
    await session.flush()

    pre = PreLabel(
        project_id=p.id,
        side="top",
        regions_json=[
            {"designator": "R1", "bbox": [0.1, 0.2, 0.05, 0.05], "confidence": 0.9, "side": "top"}
        ],
    )
    session.add(pre)
    await session.flush()

    fetched = (
        await session.execute(select(PreLabel).where(PreLabel.project_id == p.id))
    ).scalar_one()
    assert fetched.side == "top"
    assert len(fetched.regions_json) == 1
    assert fetched.regions_json[0]["designator"] == "R1"


@pytest.mark.asyncio
async def test_pre_label_unique_per_project_side(session: AsyncSession):
    """A second insert for the same (project_id, side) must violate uniqueness."""
    p = Project(name="prelabel-dup", slug=f"prelabel-dup-{uuid.uuid4().hex[:6]}")
    session.add(p)
    await session.flush()

    session.add(PreLabel(project_id=p.id, side="top", regions_json=[]))
    await session.flush()
    session.add(PreLabel(project_id=p.id, side="top", regions_json=[]))
    with pytest.raises(Exception):  # IntegrityError on UNIQUE(project_id, side)
        await session.flush()


@pytest.mark.asyncio
async def test_label_row_insert_and_unique_per_side_version(session: AsyncSession):
    """Phase 6.2 — labels are versioned per (project, side). Re-submitting a
    side increments version; (project_id, side, version) is unique."""
    p = Project(name="label-board", slug=f"label-{uuid.uuid4().hex[:6]}")
    session.add(p)
    await session.flush()

    ls_json_v1 = {
        "result": [
            {
                "id": "abc",
                "type": "rectanglelabels",
                "value": {
                    "x": 10.0,
                    "y": 20.0,
                    "width": 5.0,
                    "height": 5.0,
                    "rectanglelabels": ["R1"],
                },
                "from_name": "label",
                "to_name": "image",
                "image_rotation": 0,
                "original_width": 1000,
                "original_height": 800,
            }
        ]
    }
    lbl = Label(project_id=p.id, side="top", version=1, ls_json=ls_json_v1)
    session.add(lbl)
    await session.flush()

    fetched = (
        await session.execute(select(Label).where(Label.project_id == p.id))
    ).scalar_one()
    assert fetched.side == "top"
    assert fetched.version == 1
    assert fetched.snapshot_at is not None
    assert fetched.snapshot_at.tzinfo is not None
    assert fetched.ls_json["result"][0]["value"]["rectanglelabels"] == ["R1"]

    # Version 2 same side OK.
    session.add(Label(project_id=p.id, side="top", version=2, ls_json={"result": []}))
    await session.flush()

    # Duplicate (project, side, version) must fail.
    session.add(Label(project_id=p.id, side="top", version=2, ls_json={"result": []}))
    with pytest.raises(Exception):  # IntegrityError on UNIQUE
        await session.flush()


@pytest.mark.asyncio
async def test_label_side_check_constraint_rejects_unknown(session: AsyncSession):
    p = Project(name="label-side-chk", slug=f"label-side-{uuid.uuid4().hex[:6]}")
    session.add(p)
    await session.flush()

    session.add(Label(project_id=p.id, side="left", version=1, ls_json={"result": []}))
    with pytest.raises(Exception):  # CHECK constraint
        await session.flush()


@pytest.mark.asyncio
async def test_label_cascade_deletes_with_project(session: AsyncSession):
    p = Project(name="label-cascade", slug=f"label-cascade-{uuid.uuid4().hex[:6]}")
    session.add(p)
    await session.flush()

    session.add(Label(project_id=p.id, side="bottom", version=1, ls_json={"result": []}))
    await session.flush()
    project_id = p.id

    await session.delete(p)
    await session.flush()

    remaining = (
        await session.execute(select(Label).where(Label.project_id == project_id))
    ).scalars().all()
    assert remaining == []


@pytest.mark.asyncio
async def test_train_run_row_persists_and_links_to_adapt_run(session: AsyncSession):
    """Phase 7.2 — TrainRun tracks a service-side training job. Each row
    pins back to the AdaptRun that produced the model_dir, so we can reproduce
    the exact graphflow tree that was trained against."""
    p = Project(name="train-board", slug=f"train-{uuid.uuid4().hex[:6]}")
    session.add(p)
    await session.flush()

    adapt = AdaptRun(
        project_id=p.id,
        pcb_name="train-board",
        model_dir="/srv/models/train-board",
        inspected_count=3,
        status="ok",
    )
    session.add(adapt)
    await session.flush()

    run = TrainRun(
        project_id=p.id,
        adapt_run_id=adapt.id,
        service_job_id="job-abc-123",
        status="pending",
    )
    session.add(run)
    await session.flush()

    fetched = (
        await session.execute(select(TrainRun).where(TrainRun.project_id == p.id))
    ).scalar_one()
    assert fetched.adapt_run_id == adapt.id
    assert fetched.service_job_id == "job-abc-123"
    assert fetched.status == "pending"
    assert fetched.metrics_json is None
    assert fetched.error_text is None
    assert fetched.started_at is not None
    assert fetched.started_at.tzinfo is not None
    assert fetched.ended_at is None


@pytest.mark.asyncio
async def test_train_run_status_check_constraint_rejects_unknown(session: AsyncSession):
    """status CHECK constraint enforces the 5-value enum locked in the plan."""
    p = Project(name="train-status-chk", slug=f"train-st-{uuid.uuid4().hex[:6]}")
    session.add(p)
    await session.flush()

    adapt = AdaptRun(
        project_id=p.id,
        pcb_name="x",
        model_dir="/srv/models/x",
        inspected_count=1,
    )
    session.add(adapt)
    await session.flush()

    session.add(
        TrainRun(
            project_id=p.id,
            adapt_run_id=adapt.id,
            service_job_id="job-bogus",
            status="frobnicated",
        )
    )
    with pytest.raises(Exception):  # CHECK constraint violation
        await session.flush()


@pytest.mark.asyncio
async def test_train_run_cascade_deletes_with_project(session: AsyncSession):
    p = Project(name="train-cascade", slug=f"train-cas-{uuid.uuid4().hex[:6]}")
    session.add(p)
    await session.flush()

    adapt = AdaptRun(
        project_id=p.id,
        pcb_name="x",
        model_dir="/srv/models/x",
        inspected_count=1,
    )
    session.add(adapt)
    await session.flush()
    session.add(
        TrainRun(
            project_id=p.id,
            adapt_run_id=adapt.id,
            service_job_id="job-cascade",
            status="pending",
        )
    )
    await session.flush()
    project_id = p.id

    await session.delete(p)
    await session.flush()

    remaining = (
        await session.execute(select(TrainRun).where(TrainRun.project_id == project_id))
    ).scalars().all()
    assert remaining == []


@pytest.mark.asyncio
async def test_train_run_cascade_deletes_with_adapt_run(session: AsyncSession):
    """Deleting an AdaptRow should cascade to its TrainRuns — the lineage
    is required by audit semantics."""
    p = Project(name="train-adapt-cascade", slug=f"train-ac-{uuid.uuid4().hex[:6]}")
    session.add(p)
    await session.flush()

    adapt = AdaptRun(
        project_id=p.id,
        pcb_name="x",
        model_dir="/srv/models/x",
        inspected_count=1,
    )
    session.add(adapt)
    await session.flush()

    session.add(
        TrainRun(
            project_id=p.id,
            adapt_run_id=adapt.id,
            service_job_id="job-ac",
            status="pending",
        )
    )
    await session.flush()
    adapt_id = adapt.id

    await session.delete(adapt)
    await session.flush()

    remaining = (
        await session.execute(select(TrainRun).where(TrainRun.adapt_run_id == adapt_id))
    ).scalars().all()
    assert remaining == []


# ---------------- Phase 10.2 — deployments table ----------------


async def _seed_succeeded_train_run(session: AsyncSession) -> TrainRun:
    p = Project(name="dep-board", slug=f"dep-{uuid.uuid4().hex[:6]}")
    session.add(p)
    await session.flush()
    adapt = AdaptRun(
        project_id=p.id,
        pcb_name="dep-board",
        model_dir="/srv/models/dep",
        inspected_count=1,
        status="ok",
    )
    session.add(adapt)
    await session.flush()
    run = TrainRun(
        project_id=p.id,
        adapt_run_id=adapt.id,
        service_job_id="job-dep",
        status="succeeded",
        metrics_json={"mAP": 0.9},
    )
    session.add(run)
    await session.flush()
    return run


@pytest.mark.asyncio
async def test_deployment_row_persists_with_model_version(session: AsyncSession):
    run = await _seed_succeeded_train_run(session)
    dep = Deployment(
        project_id=run.project_id,
        train_run_id=run.id,
        model_version="2026-05-23-001",
        status="succeeded",
        edges_notified=None,
    )
    session.add(dep)
    await session.flush()

    fetched = (
        await session.execute(
            select(Deployment).where(Deployment.train_run_id == run.id)
        )
    ).scalar_one()
    assert fetched.project_id == run.project_id
    assert fetched.train_run_id == run.id
    assert fetched.model_version == "2026-05-23-001"
    assert fetched.status == "succeeded"
    assert fetched.deployed_at is not None
    assert fetched.deployed_at.tzinfo is not None
    assert fetched.edges_notified is None
    assert fetched.error_text is None


@pytest.mark.asyncio
async def test_deployment_status_check_constraint_rejects_unknown(
    session: AsyncSession,
):
    run = await _seed_succeeded_train_run(session)
    session.add(
        Deployment(
            project_id=run.project_id,
            train_run_id=run.id,
            model_version="x",
            status="frobnicated",
        )
    )
    with pytest.raises(Exception):
        await session.flush()


@pytest.mark.asyncio
async def test_deployment_cascade_deletes_with_project(session: AsyncSession):
    run = await _seed_succeeded_train_run(session)
    project_id = run.project_id
    session.add(
        Deployment(
            project_id=project_id,
            train_run_id=run.id,
            model_version="v1",
            status="succeeded",
        )
    )
    await session.flush()

    project = await session.get(Project, project_id)
    await session.delete(project)
    await session.flush()

    remaining = (
        await session.execute(
            select(Deployment).where(Deployment.project_id == project_id)
        )
    ).scalars().all()
    assert remaining == []


@pytest.mark.asyncio
async def test_deployment_cascade_deletes_with_train_run(session: AsyncSession):
    run = await _seed_succeeded_train_run(session)
    train_run_id = run.id
    session.add(
        Deployment(
            project_id=run.project_id,
            train_run_id=train_run_id,
            model_version="v2",
            status="succeeded",
        )
    )
    await session.flush()

    await session.delete(run)
    await session.flush()

    remaining = (
        await session.execute(
            select(Deployment).where(Deployment.train_run_id == train_run_id)
        )
    ).scalars().all()
    assert remaining == []


# ---------------- Phase 11.1 — edges table ----------------


@pytest.mark.asyncio
async def test_edge_row_persists_with_default_policy(session: AsyncSession):
    name = f"edge-mod-{uuid.uuid4().hex[:6]}"
    edge = Edge(
        name=name,
        webhook_url="http://edge.local:8000/api/models/refresh-cache",
    )
    session.add(edge)
    await session.flush()

    fetched = (
        await session.execute(select(Edge).where(Edge.name == name))
    ).scalar_one()
    assert fetched.webhook_url.endswith("/refresh-cache")
    # Default policy applied by server_default.
    assert fetched.version_policy == {"mode": "auto_pull_latest"}
    assert fetched.registered_at is not None
    assert fetched.registered_at.tzinfo is not None
    assert fetched.last_seen_at is None


@pytest.mark.asyncio
async def test_edge_name_unique_constraint(session: AsyncSession):
    name = f"edge-uniq-{uuid.uuid4().hex[:6]}"
    session.add(
        Edge(name=name, webhook_url="http://a.local:8000/r"),
    )
    await session.flush()

    session.add(Edge(name=name, webhook_url="http://b.local:8000/r"))
    with pytest.raises(Exception):
        await session.flush()
