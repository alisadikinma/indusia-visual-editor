"""Phase 2.3 backend: GET /api/projects/{id}/bom_items returns parsed rows."""

import csv
import io
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

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


async def _create_project(client: AsyncClient, suffix: str) -> uuid.UUID:
    slug = f"bomlist-{suffix}-{uuid.uuid4().hex[:8]}"
    r = await client.post("/api/projects", json={"name": slug, "slug": slug})
    assert r.status_code == 201
    return uuid.UUID(r.json()["data"]["id"])


def _csv_bytes(rows: list[list[str]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


@pytest.mark.asyncio
async def test_list_bom_items_empty_for_fresh_project(client: AsyncClient):
    project_id = await _create_project(client, "empty")
    r = await client.get(f"/api/projects/{project_id}/bom_items")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] is True
    assert body["data"] == []


@pytest.mark.asyncio
async def test_list_bom_items_returns_uploaded_rows_with_hints(client: AsyncClient):
    project_id = await _create_project(client, "withrows")
    payload = _csv_bytes(
        [
            ["Designator", "Value", "Package"],
            ["R1", "10k", "0805"],
            ["C4", "100uF", "Radial"],
        ]
    )
    up = await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": "bom"},
        files={"file": ("bom.csv", io.BytesIO(payload), "text/csv")},
    )
    assert up.status_code == 201

    r = await client.get(f"/api/projects/{project_id}/bom_items")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 2
    by_designator = {row["designator"]: row for row in data}
    assert by_designator["R1"]["mi_likely"] is False
    assert by_designator["R1"]["component_type"] == "smd_chip_passive"
    assert by_designator["C4"]["mi_likely"] is True
    assert by_designator["C4"]["component_type"] == "electrolytic_cap"
    assert by_designator["R1"]["inspect_scope"] == "pending"


@pytest.mark.asyncio
async def test_list_bom_items_404_for_missing_project(client: AsyncClient):
    fake_id = uuid.uuid4()
    r = await client.get(f"/api/projects/{fake_id}/bom_items")
    assert r.status_code == 404
    assert r.json()["status"] is False
