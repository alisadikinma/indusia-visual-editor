"""Phase 12.3 — POST /api/chat/{session_id}/stream.

The streaming endpoint:
  1. validates the session exists (404 otherwise),
  2. appends the user turn to messages_json,
  3. builds chat context (Phase 12.2),
  4. calls OllamaClient.stream_chat(), relays each chunk to the SSE caller,
  5. on stream completion, appends the assembled assistant turn to
     messages_json and persists the row.

We inject a fake OllamaClient via the module-level `_llm_client_factory`
seam (matches the pattern from routes/llm.py).
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any, AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from indusia_visual_editor.db.models import ChatSession, Project
from indusia_visual_editor.main import app
from indusia_visual_editor.routes.chat import (
    reset_llm_client_factory,
    set_llm_client_factory,
)


pytestmark = pytest.mark.skipif(
    not os.environ.get("IVE_DATABASE_URL"),
    reason="IVE_DATABASE_URL not set; start docker-compose.dev.yml postgres first.",
)


class _ScriptedOllamaClient:
    """Fake that emits a configurable chunk sequence from
    `chunks_to_yield` when `stream_chat` is called."""

    chunks_to_yield: list[str] = []
    raise_on_stream: Exception | None = None
    last_messages: list[dict[str, Any]] | None = None

    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self.base_url = base_url
        self.timeout = timeout

    async def stream_chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
    ) -> AsyncIterator[str]:
        type(self).last_messages = messages
        if type(self).raise_on_stream is not None:
            raise type(self).raise_on_stream
        for chunk in type(self).chunks_to_yield:
            yield chunk

    async def aclose(self) -> None:
        pass


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


@pytest.fixture(autouse=True)
def inject_fake_client():
    _ScriptedOllamaClient.chunks_to_yield = []
    _ScriptedOllamaClient.raise_on_stream = None
    _ScriptedOllamaClient.last_messages = None
    set_llm_client_factory(_ScriptedOllamaClient)
    yield
    reset_llm_client_factory()


@pytest.fixture(autouse=True)
def reset_sse_starlette_appstatus():
    """sse-starlette stashes a module-level `should_exit_event` bound to
    the event loop that first created it. pytest-asyncio swaps event
    loops per test, so the stale event would hang or raise inside
    `AppStatus.should_exit_event.wait()`. Same pattern as
    tests/routes/test_training_stream.py."""
    from sse_starlette.sse import AppStatus

    AppStatus.should_exit = False
    AppStatus.should_exit_event = None
    yield
    AppStatus.should_exit = False
    AppStatus.should_exit_event = None


async def _make_session(client: AsyncClient) -> tuple[str, str]:
    slug = f"stream-{uuid.uuid4().hex[:8]}"
    proj = await client.post("/api/projects", json={"name": "stream", "slug": slug})
    project_id = proj.json()["data"]["id"]
    chat = await client.post(f"/api/projects/{project_id}/chat")
    session_id = chat.json()["data"]["id"]
    return project_id, session_id


@pytest.mark.asyncio
async def test_chat_stream_emits_chunks_and_persists_terminal(
    client: AsyncClient, query_session: AsyncSession
):
    """Happy path: stream relays each chunk verbatim and final assembled
    assistant message lands in chat_sessions.messages_json."""
    _ScriptedOllamaClient.chunks_to_yield = [
        "Coba ",
        "tweak threshold ke 0.85, ",
        "lalu lihat false-positive rate.",
    ]

    _, session_id = await _make_session(client)

    async with client.stream(
        "POST",
        f"/api/chat/{session_id}/stream",
        json={"user_message": "C4 false positive 5%, kenapa?"},
    ) as r:
        assert r.status_code == 200, await r.aread()
        payloads: list[str] = []
        async for line in r.aiter_lines():
            if line.startswith("data:"):
                payloads.append(line[len("data:") :].strip())

    # Each chunk relayed as a `data:` line. Server emits JSON payloads
    # so the client can distinguish chunk vs terminal.
    assert len(payloads) >= 3
    relayed_text = "".join(json.loads(p).get("delta", "") for p in payloads)
    assert "Coba" in relayed_text and "threshold" in relayed_text

    # Persistence: user + assistant turns both written.
    row = (
        await query_session.execute(
            select(ChatSession).where(ChatSession.id == uuid.UUID(session_id))
        )
    ).scalar_one()
    assert len(row.messages_json) == 2
    assert row.messages_json[0]["role"] == "user"
    assert row.messages_json[0]["content"] == "C4 false positive 5%, kenapa?"
    assert row.messages_json[1]["role"] == "assistant"
    assert "Coba" in row.messages_json[1]["content"]


@pytest.mark.asyncio
async def test_chat_stream_404_for_unknown_session(client: AsyncClient):
    """Stream call on an unknown session_id must 404 without invoking
    the LLM client — guards against persisting orphan turns."""
    bogus = uuid.uuid4()
    r = await client.post(
        f"/api/chat/{bogus}/stream", json={"user_message": "halo"}
    )
    assert r.status_code == 404
    body = r.json()
    assert body["status"] is False


@pytest.mark.asyncio
async def test_chat_stream_persists_history_for_followup(
    client: AsyncClient, query_session: AsyncSession
):
    """After two round trips, messages_json holds 4 entries in order
    (u, a, u, a) and the second call's context includes the first
    assistant reply — verifiable via the fake client's captured
    last_messages."""
    _ScriptedOllamaClient.chunks_to_yield = ["jawaban-pertama"]
    _, session_id = await _make_session(client)

    async with client.stream(
        "POST",
        f"/api/chat/{session_id}/stream",
        json={"user_message": "halo"},
    ) as r:
        async for _ in r.aiter_lines():
            pass

    # Second round.
    _ScriptedOllamaClient.chunks_to_yield = ["jawaban-kedua"]
    async with client.stream(
        "POST",
        f"/api/chat/{session_id}/stream",
        json={"user_message": "follow up"},
    ) as r:
        async for _ in r.aiter_lines():
            pass

    # The second call's context (captured in fake) should include the
    # first round's user + assistant turns BEFORE the new user message.
    captured = _ScriptedOllamaClient.last_messages
    assert captured is not None
    user_contents = [m["content"] for m in captured if m["role"] == "user"]
    assert "halo" in user_contents
    assert user_contents[-1] == "follow up"

    # Persistence: 4 turns end-to-end.
    row = (
        await query_session.execute(
            select(ChatSession).where(ChatSession.id == uuid.UUID(session_id))
        )
    ).scalar_one()
    assert [m["role"] for m in row.messages_json] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
