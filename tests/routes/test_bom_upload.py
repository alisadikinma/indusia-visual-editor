"""Phase 2.2 BOM upload route + DB persistence (REPLACE strategy).

When a user uploads a BOM file via POST /api/projects/{id}/assets?kind=bom:
  - Parse the BOM bytes BEFORE persisting anything (validation up-front).
  - On parse success: write the Asset row + file, then DELETE existing
    bom_items for the project and INSERT the new drafts.
  - On parse failure: BomParseError → 422 envelope, no Asset row, no
    bom_items, no file on disk.
  - Re-upload of the SAME bytes (sha256 dedup hit) is a no-op for bom_items.
  - Re-upload of DIFFERENT bytes REPLACES the previous bom_items
    (per Phase 2.2 user decision: latest BOM wins).
"""

import csv
import io
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from indusia_visual_editor.config import get_config
from indusia_visual_editor.db.models import BomItem
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


@pytest.fixture(autouse=True)
def isolated_storage_root(tmp_path, monkeypatch):
    monkeypatch.setenv("IVE_STORAGE_ROOT", str(tmp_path))
    get_config.cache_clear() if hasattr(get_config, "cache_clear") else None
    yield tmp_path


@pytest.fixture
async def query_session():
    """Independent session for read-side assertions — the request's session is
    closed by the time the test inspects the DB."""
    engine = create_async_engine(os.environ["IVE_DATABASE_URL"], future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _create_project(client: AsyncClient, suffix: str) -> uuid.UUID:
    slug = f"bom-{suffix}-{uuid.uuid4().hex[:8]}"
    r = await client.post("/api/projects", json={"name": slug, "slug": slug})
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["data"]["id"])


def _xlsx_bytes(rows):
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _csv_bytes(rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


async def _count_bom_items(session: AsyncSession, project_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.count(BomItem.id)).where(BomItem.project_id == project_id)
    )
    return result.scalar_one()


@pytest.mark.asyncio
async def test_upload_bom_persists_bom_items(client: AsyncClient, query_session: AsyncSession):
    project_id = await _create_project(client, "persist")
    payload = _xlsx_bytes(
        [
            ["Designator", "Value", "Package", "Qty"],
            ["R1", "10k", "0805", 1],
            ["C4", "100uF", "Radial", 1],
            ["U7", "STM32F4", "LQFP-100", 1],
        ]
    )

    response = await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": "bom"},
        files={"file": ("bom.xlsx", io.BytesIO(payload), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] is True

    count = await _count_bom_items(query_session, project_id)
    assert count == 3


@pytest.mark.asyncio
async def test_upload_bom_links_items_to_project(client: AsyncClient, query_session: AsyncSession):
    project_id = await _create_project(client, "link")
    payload = _csv_bytes(
        [
            ["Designator", "Value"],
            ["R1", "10k"],
            ["C4", "100nF"],
        ]
    )

    response = await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": "bom"},
        files={"file": ("bom.csv", io.BytesIO(payload), "text/csv")},
    )
    assert response.status_code == 201

    rows = (
        await query_session.execute(
            select(BomItem).where(BomItem.project_id == project_id)
        )
    ).scalars().all()
    assert {r.designator for r in rows} == {"R1", "C4"}
    assert all(r.project_id == project_id for r in rows)


@pytest.mark.asyncio
async def test_upload_bad_bom_returns_422_and_no_rows(
    client: AsyncClient, query_session: AsyncSession, isolated_storage_root
):
    project_id = await _create_project(client, "bad")
    bad = b"\x00\x01\x02 not a real xlsx"

    response = await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": "bom"},
        files={"file": ("garbage.xlsx", io.BytesIO(bad), "application/octet-stream")},
    )
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["status"] is False

    count = await _count_bom_items(query_session, project_id)
    assert count == 0, "no bom_items should be persisted on parse failure"

    project_dir = isolated_storage_root / str(project_id) / "bom"
    files = list(project_dir.glob("*")) if project_dir.exists() else []
    assert files == [], "no file should be written on parse failure"


@pytest.mark.asyncio
async def test_reupload_bom_replaces_previous_items(
    client: AsyncClient, query_session: AsyncSession
):
    project_id = await _create_project(client, "replace")

    first = _csv_bytes(
        [
            ["Designator", "Value"],
            ["R1", "10k"],
            ["R2", "20k"],
            ["R3", "30k"],
        ]
    )
    r1 = await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": "bom"},
        files={"file": ("bom1.csv", io.BytesIO(first), "text/csv")},
    )
    assert r1.status_code == 201
    assert await _count_bom_items(query_session, project_id) == 3

    second = _csv_bytes(
        [
            ["Designator", "Value"],
            ["C4", "100nF"],
            ["U7", "STM32"],
        ]
    )
    r2 = await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": "bom"},
        files={"file": ("bom2.csv", io.BytesIO(second), "text/csv")},
    )
    assert r2.status_code == 201

    final = (
        await query_session.execute(
            select(BomItem).where(BomItem.project_id == project_id)
        )
    ).scalars().all()
    designators = {r.designator for r in final}
    assert designators == {"C4", "U7"}, (
        f"REPLACE strategy: old R1/R2/R3 must be gone, got {designators}"
    )


@pytest.mark.asyncio
async def test_upload_bom_persists_mi_classifier_hints(
    client: AsyncClient, query_session: AsyncSession
):
    """Phase 2.2b: mi_likely + component_type must be set per row after parse."""
    project_id = await _create_project(client, "classify")
    payload = _csv_bytes(
        [
            ["Designator", "Value", "Package"],
            ["R1", "10k", "0805"],
            ["C4", "100uF/16V", "Radial"],
            ["J1", "USB-C", ""],
        ]
    )

    r = await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": "bom"},
        files={"file": ("bom.csv", io.BytesIO(payload), "text/csv")},
    )
    assert r.status_code == 201, r.text

    rows = (
        await query_session.execute(
            select(BomItem).where(BomItem.project_id == project_id)
        )
    ).scalars().all()
    by_designator = {r.designator: r for r in rows}

    assert by_designator["R1"].mi_likely is False
    assert by_designator["R1"].component_type == "smd_chip_passive"

    assert by_designator["C4"].mi_likely is True
    assert by_designator["C4"].component_type == "electrolytic_cap"

    # J1: no package, designator prefix J → connector, MI-likely.
    assert by_designator["J1"].mi_likely is True
    assert by_designator["J1"].component_type == "connector"


@pytest.mark.asyncio
async def test_reupload_identical_bom_dedups_no_change(
    client: AsyncClient, query_session: AsyncSession
):
    project_id = await _create_project(client, "dedup")
    payload = _csv_bytes(
        [
            ["Designator", "Value"],
            ["R1", "10k"],
        ]
    )

    r1 = await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": "bom"},
        files={"file": ("a.csv", io.BytesIO(payload), "text/csv")},
    )
    assert r1.status_code == 201
    first_asset_id = r1.json()["data"]["id"]

    r2 = await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": "bom"},
        files={"file": ("b.csv", io.BytesIO(payload), "text/csv")},
    )
    assert r2.status_code == 200, "dedup hit returns 200"
    assert r2.json()["data"]["id"] == first_asset_id
    assert await _count_bom_items(query_session, project_id) == 1
