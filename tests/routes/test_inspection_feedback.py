"""Inspection-feedback route tests (Phases D + E).

DB-gated: SKIPS when IVE_DATABASE_URL is unset (start docker-compose.dev.yml
postgres first). Exercises ingest (multipart Form + optional ROI), list,
curate, and the inspection-logic promote gate against the live FastAPI app.
"""

from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from indusia_visual_editor.db.models import (
    DefectExample,
    InspectionFeedback,
    Project,
    ProjectStatus,
)
from indusia_visual_editor.main import app


DB_URL = os.environ.get("IVE_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DB_URL,
    reason="IVE_DATABASE_URL not set; start docker-compose.dev.yml postgres first.",
)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def query_session():
    engine = create_async_engine(DB_URL, echo=False, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _make_project(session: AsyncSession) -> uuid.UUID:
    project = Project(
        name="FB-route",
        slug=f"fb-route-{uuid.uuid4().hex[:8]}",
        status=ProjectStatus.DEPLOYED,
    )
    session.add(project)
    await session.commit()
    return project.id


# ---------------- Phase D — ingest + list ----------------


@pytest.mark.asyncio
async def test_post_inspection_feedback_persists_row(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _make_project(query_session)
    r = await client.post(
        f"/api/projects/{pid}/inspection-feedback",
        data={
            "designator": "R1",
            "model_verdict": "pass",
            "operator_mark": "escape",
            "defect_criterion": "missing_component",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] is True
    fid = body["data"]["id"]

    row = (
        await query_session.execute(
            select(InspectionFeedback).where(InspectionFeedback.id == uuid.UUID(fid))
        )
    ).scalar_one()
    assert row.operator_mark == "escape"
    assert row.status == "new"
    assert row.roi_path is None


@pytest.mark.asyncio
async def test_post_inspection_feedback_with_roi_saves_file_meta(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _make_project(query_session)
    r = await client.post(
        f"/api/projects/{pid}/inspection-feedback",
        data={
            "model_verdict": "pass",
            "operator_mark": "escape",
            "defect_criterion": "lifted_pin",
        },
        files={"file": ("roi.jpg", b"\xff\xd8\xff\xe0roi-bytes", "image/jpeg")},
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["roi_path"] is not None
    assert data["roi_path"].endswith(".jpg")
    assert data["roi_sha256"] is not None


@pytest.mark.asyncio
async def test_post_inspection_feedback_404_unknown_project(client: AsyncClient):
    bogus = uuid.uuid4()
    r = await client.post(
        f"/api/projects/{bogus}/inspection-feedback",
        data={"model_verdict": "pass", "operator_mark": "confirmed"},
    )
    assert r.status_code == 404
    assert r.json()["status"] is False


@pytest.mark.asyncio
async def test_get_inspection_feedback_filters_by_status(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _make_project(query_session)
    # one 'new', one dismissed.
    r1 = await client.post(
        f"/api/projects/{pid}/inspection-feedback",
        data={"model_verdict": "pass", "operator_mark": "escape"},
    )
    new_id = r1.json()["data"]["id"]
    r2 = await client.post(
        f"/api/projects/{pid}/inspection-feedback",
        data={"model_verdict": "fail", "operator_mark": "overkill"},
    )
    other_id = r2.json()["data"]["id"]
    await client.put(
        f"/api/inspection-feedback/{other_id}",
        json={"status": "dismissed"},
    )

    r = await client.get(
        f"/api/projects/{pid}/inspection-feedback", params={"status": "new"}
    )
    assert r.status_code == 200
    ids = {row["id"] for row in r.json()["data"]}
    assert new_id in ids
    assert other_id not in ids


# ---------------- Phase E — curate + promote ----------------


@pytest.mark.asyncio
async def test_put_curate_updates_status_and_mark(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _make_project(query_session)
    r = await client.post(
        f"/api/projects/{pid}/inspection-feedback",
        data={"model_verdict": "fail", "operator_mark": "overkill"},
    )
    fid = r.json()["data"]["id"]

    r = await client.put(
        f"/api/inspection-feedback/{fid}",
        json={"operator_mark": "confirmed", "status": "curated"},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["operator_mark"] == "confirmed"
    assert data["status"] == "curated"


@pytest.mark.asyncio
async def test_put_curate_404_unknown(client: AsyncClient):
    bogus = uuid.uuid4()
    r = await client.put(
        f"/api/inspection-feedback/{bogus}", json={"status": "dismissed"}
    )
    assert r.status_code == 404
    assert r.json()["status"] is False


@pytest.mark.asyncio
async def test_promote_creates_defect_example(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _make_project(query_session)
    r = await client.post(
        f"/api/projects/{pid}/inspection-feedback",
        data={
            "designator": "U3",
            "model_verdict": "pass",
            "operator_mark": "escape",
            "defect_criterion": "missing_component",
        },
        files={"file": ("roi.jpg", b"\xff\xd8roi", "image/jpeg")},
    )
    fid = r.json()["data"]["id"]

    r = await client.post(f"/api/inspection-feedback/{fid}/promote")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] is True
    example_id = body["data"]["id"]

    ex = (
        await query_session.execute(
            select(DefectExample).where(DefectExample.id == uuid.UUID(example_id))
        )
    ).scalar_one()
    assert ex.defect_criterion == "missing_component"
    assert ex.source_feedback_id == uuid.UUID(fid)

    # source row flips to promoted.
    fb = (
        await query_session.execute(
            select(InspectionFeedback).where(InspectionFeedback.id == uuid.UUID(fid))
        )
    ).scalar_one()
    assert fb.status == "promoted"


@pytest.mark.asyncio
async def test_promote_rejects_overkill(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _make_project(query_session)
    r = await client.post(
        f"/api/projects/{pid}/inspection-feedback",
        data={
            "model_verdict": "fail",
            "operator_mark": "overkill",
            "defect_criterion": "missing_component",
        },
        files={"file": ("roi.jpg", b"\xff\xd8roi-ok", "image/jpeg")},
    )
    fid = r.json()["data"]["id"]

    r = await client.post(f"/api/inspection-feedback/{fid}/promote")
    assert r.status_code == 409, r.text
    assert r.json()["status"] is False


@pytest.mark.asyncio
async def test_promote_rejects_missing_roi(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _make_project(query_session)
    r = await client.post(
        f"/api/projects/{pid}/inspection-feedback",
        data={
            "model_verdict": "pass",
            "operator_mark": "escape",
            "defect_criterion": "missing_component",
        },
    )
    fid = r.json()["data"]["id"]

    r = await client.post(f"/api/inspection-feedback/{fid}/promote")
    assert r.status_code == 409, r.text
    assert r.json()["status"] is False


@pytest.mark.asyncio
async def test_promote_rejects_invalid_criterion(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _make_project(query_session)
    r = await client.post(
        f"/api/projects/{pid}/inspection-feedback",
        data={
            "model_verdict": "pass",
            "operator_mark": "escape",
            "defect_criterion": "not_a_real_criterion",
        },
        files={"file": ("roi.jpg", b"\xff\xd8roi-x", "image/jpeg")},
    )
    fid = r.json()["data"]["id"]

    r = await client.post(f"/api/inspection-feedback/{fid}/promote")
    assert r.status_code == 409, r.text
    assert r.json()["status"] is False


@pytest.mark.asyncio
async def test_promote_404_unknown(client: AsyncClient):
    bogus = uuid.uuid4()
    r = await client.post(f"/api/inspection-feedback/{bogus}/promote")
    assert r.status_code == 404
    assert r.json()["status"] is False


@pytest.mark.asyncio
async def test_promote_twice_rejected(
    client: AsyncClient, query_session: AsyncSession
):
    """Second promote on an already-promoted row is refused (no duplicate
    DefectExample for the same source feedback)."""
    pid = await _make_project(query_session)
    r = await client.post(
        f"/api/projects/{pid}/inspection-feedback",
        data={
            "model_verdict": "pass",
            "operator_mark": "escape",
            "defect_criterion": "missing_component",
        },
        files={"file": ("roi.jpg", b"\xff\xd8roi-twice", "image/jpeg")},
    )
    fid = r.json()["data"]["id"]

    first = await client.post(f"/api/inspection-feedback/{fid}/promote")
    assert first.status_code == 201, first.text
    second = await client.post(f"/api/inspection-feedback/{fid}/promote")
    assert second.status_code == 409, second.text

    count = len(
        (
            await query_session.execute(
                select(DefectExample).where(
                    DefectExample.source_feedback_id == uuid.UUID(fid)
                )
            )
        )
        .scalars()
        .all()
    )
    assert count == 1


@pytest.mark.asyncio
async def test_list_all_feedback_cross_project(
    client: AsyncClient, query_session: AsyncSession
):
    """The root /api/inspection-feedback inbox lists across projects and
    honours the ?status= filter (powers the global /feedback screen)."""
    pid_a = await _make_project(query_session)
    pid_b = await _make_project(query_session)
    ra = await client.post(
        f"/api/projects/{pid_a}/inspection-feedback",
        data={"model_verdict": "fail", "operator_mark": "escape"},
    )
    rb = await client.post(
        f"/api/projects/{pid_b}/inspection-feedback",
        data={"model_verdict": "pass", "operator_mark": "overkill"},
    )
    id_a = ra.json()["data"]["id"]
    id_b = rb.json()["data"]["id"]

    r = await client.get("/api/inspection-feedback")
    assert r.status_code == 200, r.text
    all_ids = {row["id"] for row in r.json()["data"]}
    assert {id_a, id_b} <= all_ids

    r = await client.get("/api/inspection-feedback", params={"status": "new"})
    assert {id_a, id_b} <= {row["id"] for row in r.json()["data"]}
