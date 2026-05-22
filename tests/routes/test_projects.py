"""Phase 1.2 Projects CRUD API tests.

All 5 endpoints exercise the live `ive` DB at localhost:5433 via the FastAPI
test app. Each test uses a unique slug suffix so concurrent runs and
re-runs don't collide. The 0001 schema is the source of truth.

Response shape on every path (success AND error) is `{status, message, data}`
per CLAUDE.md §6.1 — this is also enforced in assertions.
"""

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from indusia_visual_editor.main import app


pytestmark = pytest.mark.skipif(
    not os.environ.get("IVE_DATABASE_URL"),
    reason="IVE_DATABASE_URL not set; start docker-compose.dev.yml postgres first.",
)


def _unique(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:8]}"


def _assert_envelope(body: dict, expect_status: bool) -> None:
    assert set(body.keys()) == {"status", "message", "data"}, body
    assert body["status"] is expect_status
    assert isinstance(body["message"], str)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient):
    slug = _unique("crt")
    response = await client.post(
        "/api/projects",
        json={"name": "Create test", "slug": slug},
    )

    assert response.status_code == 201
    body = response.json()
    _assert_envelope(body, expect_status=True)
    assert body["data"]["slug"] == slug
    assert body["data"]["status"] == "drafting"
    assert "id" in body["data"]


@pytest.mark.asyncio
async def test_create_project_duplicate_slug_returns_409(client: AsyncClient):
    slug = _unique("dup")
    first = await client.post(
        "/api/projects", json={"name": "First", "slug": slug}
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/projects", json={"name": "Second", "slug": slug}
    )
    assert second.status_code == 409
    _assert_envelope(second.json(), expect_status=False)


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient):
    slug = _unique("lst")
    await client.post("/api/projects", json={"name": "List me", "slug": slug})

    response = await client.get("/api/projects")
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body, expect_status=True)
    assert isinstance(body["data"], list)
    slugs = [p["slug"] for p in body["data"]]
    assert slug in slugs


@pytest.mark.asyncio
async def test_get_project(client: AsyncClient):
    slug = _unique("get")
    created = await client.post(
        "/api/projects", json={"name": "Get me", "slug": slug}
    )
    project_id = created.json()["data"]["id"]

    response = await client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body, expect_status=True)
    assert body["data"]["id"] == project_id
    assert body["data"]["slug"] == slug


@pytest.mark.asyncio
async def test_get_project_404_envelope(client: AsyncClient):
    missing = uuid.uuid4()
    response = await client.get(f"/api/projects/{missing}")
    assert response.status_code == 404
    _assert_envelope(response.json(), expect_status=False)


@pytest.mark.asyncio
async def test_update_project(client: AsyncClient):
    slug = _unique("upd")
    created = await client.post(
        "/api/projects", json={"name": "Old", "slug": slug}
    )
    project_id = created.json()["data"]["id"]

    response = await client.put(
        f"/api/projects/{project_id}",
        json={"name": "New", "status": "training"},
    )
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body, expect_status=True)
    assert body["data"]["name"] == "New"
    assert body["data"]["status"] == "training"
    assert body["data"]["slug"] == slug


@pytest.mark.asyncio
async def test_delete_project(client: AsyncClient):
    slug = _unique("del")
    created = await client.post(
        "/api/projects", json={"name": "Doomed", "slug": slug}
    )
    project_id = created.json()["data"]["id"]

    response = await client.delete(f"/api/projects/{project_id}")
    assert response.status_code == 200
    _assert_envelope(response.json(), expect_status=True)

    follow_up = await client.get(f"/api/projects/{project_id}")
    assert follow_up.status_code == 404
