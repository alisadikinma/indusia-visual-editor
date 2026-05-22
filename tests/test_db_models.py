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
    Asset,
    AssetKind,
    BomItem,
    InspectScope,
    PreLabel,
    Project,
    ProjectStatus,
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
