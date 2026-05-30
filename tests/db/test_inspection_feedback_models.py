"""Inspection-feedback ORM roundtrip (v1 inspection-feedback loop, Phase A).

Exercises the live dev Postgres (NOT SQLite) so the CHECK constraints on
`operator_mark` / `model_verdict` / `status`, the JSONB-free text columns,
and the project-cascade deletes all behave exactly as in production.

Each test runs in its own transaction and rolls back at teardown — the dev
DB is never polluted. Skips entirely when IVE_DATABASE_URL is unset.
"""

import os
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from indusia_visual_editor.db.models import (
    DefectExample,
    InspectionFeedback,
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


def _unique_slug(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@pytest.mark.asyncio
async def test_inspection_feedback_roundtrip(session: AsyncSession):
    project = Project(
        name="FB-roundtrip",
        slug=_unique_slug("fb-roundtrip"),
        status=ProjectStatus.DEPLOYED,
    )
    session.add(project)
    await session.flush()

    fb = InspectionFeedback(
        project_id=project.id,
        designator="R12",
        model_verdict="pass",
        operator_mark="escape",
        defect_criterion="missing_component",
        roi_path=f"{project.id}/feedback_roi/abc123.jpg",
        roi_sha256="abc123" + "0" * 58,
    )
    session.add(fb)
    await session.flush()
    await session.refresh(fb)

    assert isinstance(fb.id, uuid.UUID)
    assert fb.status == "new"  # default
    assert fb.created_at is not None
    assert fb.created_at.tzinfo is not None, "timestamps must be timezone-aware"

    fetched = (
        await session.execute(
            select(InspectionFeedback).where(InspectionFeedback.id == fb.id)
        )
    ).scalar_one()
    assert fetched.operator_mark == "escape"
    assert fetched.defect_criterion == "missing_component"


@pytest.mark.asyncio
async def test_defect_example_roundtrip(session: AsyncSession):
    project = Project(
        name="DE-roundtrip",
        slug=_unique_slug("de-roundtrip"),
        status=ProjectStatus.DEPLOYED,
    )
    session.add(project)
    await session.flush()

    fb = InspectionFeedback(
        project_id=project.id,
        model_verdict="pass",
        operator_mark="escape",
        defect_criterion="lifted_pin",
        roi_path=f"{project.id}/feedback_roi/def456.jpg",
        roi_sha256="def456" + "0" * 58,
    )
    session.add(fb)
    await session.flush()

    example = DefectExample(
        project_id=project.id,
        source_feedback_id=fb.id,
        designator="U3",
        defect_criterion="lifted_pin",
        roi_path=fb.roi_path,
        roi_sha256=fb.roi_sha256,
    )
    session.add(example)
    await session.flush()
    await session.refresh(example)

    assert isinstance(example.id, uuid.UUID)
    assert example.created_at is not None
    assert example.source_feedback_id == fb.id


@pytest.mark.asyncio
async def test_check_rejects_bad_operator_mark(session: AsyncSession):
    project = Project(
        name="FB-badmark",
        slug=_unique_slug("fb-badmark"),
        status=ProjectStatus.DEPLOYED,
    )
    session.add(project)
    await session.flush()

    fb = InspectionFeedback(
        project_id=project.id,
        model_verdict="pass",
        operator_mark="not-a-real-mark",
    )
    session.add(fb)
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_project_cascade_deletes_feedback(session: AsyncSession):
    project = Project(
        name="FB-cascade",
        slug=_unique_slug("fb-cascade"),
        status=ProjectStatus.DEPLOYED,
    )
    session.add(project)
    await session.flush()

    fb = InspectionFeedback(
        project_id=project.id,
        model_verdict="fail",
        operator_mark="confirmed",
    )
    session.add(fb)
    await session.flush()
    fb_id = fb.id

    await session.delete(project)
    await session.flush()

    gone = (
        await session.execute(
            select(InspectionFeedback).where(InspectionFeedback.id == fb_id)
        )
    ).scalar_one_or_none()
    assert gone is None
