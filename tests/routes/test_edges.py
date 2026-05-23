"""Phase 11.1 — edges registry CRUD + Phase 11.3 manual pin route.

The `edges` table holds the registry of physical edge nodes that pull
weights from the production model registry. Each row records the edge's
human-readable name, the webhook URL the visual-editor calls when a
deployment ships, and a per-edge `version_policy` JSONB that gates
whether the edge auto-pulls the latest version or stays pinned.
"""

from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from indusia_visual_editor.db.models import Edge
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
async def query_session():
    engine = create_async_engine(os.environ["IVE_DATABASE_URL"], future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
    await engine.dispose()


def _unique_name(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@pytest.mark.asyncio
async def test_post_edges_registers_edge_with_default_policy(
    client: AsyncClient, query_session: AsyncSession
):
    name = _unique_name("edge-line-a")
    r = await client.post(
        "/api/edges",
        json={"name": name, "webhook_url": "http://edge-a.local:8000/api/models/refresh-cache"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] is True
    data = body["data"]
    assert data["name"] == name
    assert data["webhook_url"].endswith("/refresh-cache")
    # Default policy when caller omits version_policy.
    assert data["version_policy"] == {"mode": "auto_pull_latest"}
    assert data["registered_at"] is not None
    assert data["last_seen_at"] is None

    # Row persisted.
    row = (
        await query_session.execute(select(Edge).where(Edge.name == name))
    ).scalar_one()
    assert row.version_policy == {"mode": "auto_pull_latest"}


@pytest.mark.asyncio
async def test_post_edges_409_on_duplicate_name(client: AsyncClient):
    name = _unique_name("edge-dup")
    r1 = await client.post(
        "/api/edges",
        json={"name": name, "webhook_url": "http://x.local:8000/refresh"},
    )
    assert r1.status_code == 201
    r2 = await client.post(
        "/api/edges",
        json={"name": name, "webhook_url": "http://y.local:8000/refresh"},
    )
    assert r2.status_code == 409, r2.text
    assert r2.json()["status"] is False


@pytest.mark.asyncio
async def test_get_edges_lists_registered_edges(client: AsyncClient):
    names = {_unique_name("list-a"), _unique_name("list-b")}
    for n in names:
        r = await client.post(
            "/api/edges",
            json={"name": n, "webhook_url": f"http://{n}.local:8000/r"},
        )
        assert r.status_code == 201

    r = await client.get("/api/edges")
    assert r.status_code == 200
    rows = r.json()["data"]
    returned = {row["name"] for row in rows}
    assert names.issubset(returned)


@pytest.mark.asyncio
async def test_put_edge_updates_policy(
    client: AsyncClient, query_session: AsyncSession
):
    name = _unique_name("policy-up")
    r = await client.post(
        "/api/edges",
        json={"name": name, "webhook_url": "http://policy.local:8000/r"},
    )
    edge_id = r.json()["data"]["id"]

    new_policy = {"mode": "auto_pull_latest", "min_map_threshold": 0.85}
    r = await client.put(
        f"/api/edges/{edge_id}",
        json={"version_policy": new_policy},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["version_policy"] == new_policy

    row = (
        await query_session.execute(select(Edge).where(Edge.name == name))
    ).scalar_one()
    assert row.version_policy == new_policy


@pytest.mark.asyncio
async def test_put_edge_404_for_unknown_id(client: AsyncClient):
    bogus = uuid.uuid4()
    r = await client.put(
        f"/api/edges/{bogus}",
        json={"version_policy": {"mode": "auto_pull_latest"}},
    )
    assert r.status_code == 404
    assert r.json()["status"] is False


@pytest.mark.asyncio
async def test_post_edges_422_on_invalid_url(client: AsyncClient):
    """Validation gate — webhook_url must look like a URL. If we accept
    arbitrary strings the notify service will fail per-edge at runtime
    instead of at registration time."""
    r = await client.post(
        "/api/edges",
        json={"name": _unique_name("bad-url"), "webhook_url": "not-a-url"},
    )
    assert r.status_code == 422
    assert r.json()["status"] is False


# ---------------- Phase 11.3 — manual pin route ----------------


@pytest.mark.asyncio
async def test_put_edge_pin_sets_pinned_policy(
    client: AsyncClient, query_session: AsyncSession
):
    """Pinning rolls the edge back to an explicit (model_name, version)
    pair — the next webhook the edge receives names that target instead
    of `latest`."""
    name = _unique_name("pin-target")
    r = await client.post(
        "/api/edges",
        json={"name": name, "webhook_url": "http://pin.local:8000/r"},
    )
    edge_id = r.json()["data"]["id"]

    r = await client.put(
        f"/api/edges/{edge_id}/pin",
        json={"model_name": "pcb_42", "version": "20260101-120000-abc123"},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["version_policy"] == {
        "mode": "pinned",
        "model_name": "pcb_42",
        "version": "20260101-120000-abc123",
    }


@pytest.mark.asyncio
async def test_put_edge_unpin_resets_to_auto_pull_latest(client: AsyncClient):
    """Calling pin without model_name+version resets the edge back to
    auto-pull mode — the explicit unpin path."""
    name = _unique_name("unpin")
    r = await client.post(
        "/api/edges",
        json={"name": name, "webhook_url": "http://unpin.local:8000/r"},
    )
    edge_id = r.json()["data"]["id"]

    # Pin first.
    r = await client.put(
        f"/api/edges/{edge_id}/pin",
        json={"model_name": "pcb_x", "version": "v1"},
    )
    assert r.status_code == 200

    # Now unpin via empty body.
    r = await client.put(f"/api/edges/{edge_id}/pin", json={})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["version_policy"] == {"mode": "auto_pull_latest"}


@pytest.mark.asyncio
async def test_put_edge_pin_404_for_unknown_id(client: AsyncClient):
    bogus = uuid.uuid4()
    r = await client.put(
        f"/api/edges/{bogus}/pin",
        json={"model_name": "x", "version": "v1"},
    )
    assert r.status_code == 404
    assert r.json()["status"] is False
