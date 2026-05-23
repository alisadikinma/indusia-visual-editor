"""Phase 12.1 — chat session table + history APIs.

The `chat_sessions` table holds the rolling conversation history between
operator and Gemma advisor. One row per chat session (operator may open
multiple sessions per project — eg "C4 false positives" vs "training time
too slow"). Messages live as a JSONB array of {role, content, ts}; the
streaming SSE endpoint (Phase 12.3) appends both user and assistant turns
once the assistant stream terminates.
"""

from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from indusia_visual_editor.db.models import ChatSession, Project
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


async def _make_project(client: AsyncClient, slug_prefix: str = "chat") -> str:
    slug = f"{slug_prefix}-{uuid.uuid4().hex[:8]}"
    r = await client.post(
        "/api/projects", json={"name": f"{slug_prefix} fixture", "slug": slug}
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


@pytest.mark.asyncio
async def test_chat_session_row_persists(query_session: AsyncSession):
    """Bedrock test: ChatSession row inserts with empty messages_json
    default and is reachable via SQLAlchemy query. If this fails the
    migration didn't run."""
    # Need a Project FK; insert one directly.
    proj = Project(name="chat-bed", slug=f"chat-bed-{uuid.uuid4().hex[:8]}")
    query_session.add(proj)
    await query_session.flush()

    row = ChatSession(project_id=proj.id)
    query_session.add(row)
    await query_session.flush()
    await query_session.refresh(row)

    assert row.id is not None
    assert row.messages_json == []
    assert row.created_at is not None
    assert row.updated_at is not None


@pytest.mark.asyncio
async def test_post_chat_creates_session(
    client: AsyncClient, query_session: AsyncSession
):
    project_id = await _make_project(client, "post-chat")
    r = await client.post(f"/api/projects/{project_id}/chat")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] is True
    data = body["data"]
    assert "id" in data
    assert data["project_id"] == project_id
    assert data["messages_json"] == []

    # Row persisted.
    row = (
        await query_session.execute(
            select(ChatSession).where(ChatSession.id == uuid.UUID(data["id"]))
        )
    ).scalar_one()
    assert row.project_id == uuid.UUID(project_id)


@pytest.mark.asyncio
async def test_get_project_chat_lists_sessions(client: AsyncClient):
    project_id = await _make_project(client, "list-chat")
    # Create two sessions.
    s1 = (await client.post(f"/api/projects/{project_id}/chat")).json()["data"]["id"]
    s2 = (await client.post(f"/api/projects/{project_id}/chat")).json()["data"]["id"]

    r = await client.get(f"/api/projects/{project_id}/chat")
    assert r.status_code == 200, r.text
    rows = r.json()["data"]
    ids = {row["id"] for row in rows}
    assert {s1, s2}.issubset(ids)


@pytest.mark.asyncio
async def test_get_chat_session_returns_full_messages(client: AsyncClient):
    project_id = await _make_project(client, "get-chat")
    session_id = (
        await client.post(f"/api/projects/{project_id}/chat")
    ).json()["data"]["id"]

    r = await client.get(f"/api/chat/{session_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] is True
    data = body["data"]
    assert data["id"] == session_id
    assert data["messages_json"] == []


@pytest.mark.asyncio
async def test_get_chat_session_404_for_unknown_id(client: AsyncClient):
    bogus = uuid.uuid4()
    r = await client.get(f"/api/chat/{bogus}")
    assert r.status_code == 404
    assert r.json()["status"] is False
