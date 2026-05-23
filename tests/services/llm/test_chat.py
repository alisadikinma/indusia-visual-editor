"""Phase 12.2 — chat context builder.

The context builder pulls together:
- The system prompt (from prompts/advisor.md)
- Project metadata (name, status, last train run metrics)
- Last N=20 chat turns from chat_sessions.messages_json
- The freshly typed user message
- Token-budget enforcement: aggregate stays under ~200K Gemma 4 tokens

Output: an ordered list of `{role, content}` messages ready for
`OllamaClient.chat()` / `stream_chat()`. The builder owns truncation
strategy — drop oldest turns first, never truncate the system prompt or
the active user message.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from indusia_visual_editor.db.models import ChatSession, Project, TrainRun, AdaptRun
from indusia_visual_editor.services.llm.chat import (
    MAX_TURNS,
    TOKEN_BUDGET_CHARS,
    build_chat_context,
)


pytestmark = pytest.mark.skipif(
    not os.environ.get("IVE_DATABASE_URL"),
    reason="IVE_DATABASE_URL not set; start docker-compose.dev.yml postgres first.",
)


@pytest.fixture
async def db_session():
    engine = create_async_engine(os.environ["IVE_DATABASE_URL"], future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _make_project_and_session(
    db: AsyncSession, *, turns: list[dict] | None = None
) -> tuple[uuid.UUID, uuid.UUID]:
    proj = Project(name="ctx-builder", slug=f"ctx-{uuid.uuid4().hex[:8]}")
    db.add(proj)
    await db.flush()

    sess = ChatSession(project_id=proj.id, messages_json=turns or [])
    db.add(sess)
    await db.flush()
    return proj.id, sess.id


@pytest.mark.asyncio
async def test_build_chat_context_includes_recent_metrics_and_turns(
    db_session: AsyncSession,
):
    """The happy path: system prompt + project line + (optional metrics) +
    history + new user message — in exactly that order."""
    turns = [
        {"role": "user", "content": "halo bro", "ts": "2026-05-23T10:00:00Z"},
        {
            "role": "assistant",
            "content": "halo, ada yang bisa dibantu?",
            "ts": "2026-05-23T10:00:02Z",
        },
    ]
    project_id, session_id = await _make_project_and_session(db_session, turns=turns)

    # Seed an adapt_run + train_run with metrics so we can assert injection.
    adapt = AdaptRun(
        project_id=project_id,
        pcb_name="pcb_x",
        model_dir="/tmp/model",
        inspected_count=10,
    )
    db_session.add(adapt)
    await db_session.flush()

    tr = TrainRun(
        project_id=project_id,
        adapt_run_id=adapt.id,
        service_job_id="job-abc",
        status="succeeded",
        metrics_json={"map": 0.91, "per_component_f1": {"R1": 0.95}},
    )
    db_session.add(tr)
    await db_session.flush()

    messages = await build_chat_context(
        db_session,
        project_id=project_id,
        session_id=session_id,
        user_message="C4 false-positive 5% di line 3, kenapa?",
    )

    # Shape: list[dict] with role/content keys
    assert isinstance(messages, list)
    assert all({"role", "content"} <= set(m.keys()) for m in messages)

    # System prompt is first.
    assert messages[0]["role"] == "system"
    assert len(messages[0]["content"]) > 50

    # Last message is the new user message — verbatim.
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "C4 false-positive 5% di line 3, kenapa?"

    # Prior history present in correct order.
    user_contents = [m["content"] for m in messages if m["role"] == "user"]
    assert "halo bro" in user_contents
    assert user_contents.index("halo bro") < user_contents.index(
        "C4 false-positive 5% di line 3, kenapa?"
    )

    # Metrics injected into the system or context message.
    blob = "\n".join(m["content"] for m in messages)
    assert "0.91" in blob or "mAP" in blob.lower()


@pytest.mark.asyncio
async def test_build_chat_context_truncates_to_last_20_turns(
    db_session: AsyncSession,
):
    """If chat history has 50 turns, only the most-recent MAX_TURNS=20
    survive into the prompt. Older turns drop silently."""
    long_history = [
        {
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"turn-{i}",
            "ts": "2026-05-23T10:00:00Z",
        }
        for i in range(50)
    ]
    project_id, session_id = await _make_project_and_session(
        db_session, turns=long_history
    )

    messages = await build_chat_context(
        db_session,
        project_id=project_id,
        session_id=session_id,
        user_message="ringkasan dong",
    )

    # Strip system prompt + new user message; what's left is history.
    history = [m for m in messages[1:-1] if m["content"].startswith("turn-")]
    assert len(history) == MAX_TURNS
    # Most-recent 20 means turn-30..turn-49 inclusive.
    assert history[0]["content"] == "turn-30"
    assert history[-1]["content"] == "turn-49"


@pytest.mark.asyncio
async def test_build_chat_context_enforces_token_budget(
    db_session: AsyncSession,
):
    """If after the 20-turn cap the aggregate is still over budget, drop
    further from the front. System prompt and new user message stay."""
    # Each turn = 50_000 chars. 20 turns = 1M chars, way over budget.
    big = "x" * 50_000
    long_history = [
        {
            "role": "user" if i % 2 == 0 else "assistant",
            "content": big,
            "ts": "2026-05-23T10:00:00Z",
        }
        for i in range(20)
    ]
    project_id, session_id = await _make_project_and_session(
        db_session, turns=long_history
    )

    messages = await build_chat_context(
        db_session,
        project_id=project_id,
        session_id=session_id,
        user_message="masih muat ga?",
    )

    total = sum(len(m["content"]) for m in messages)
    assert total <= TOKEN_BUDGET_CHARS, f"budget exceeded: {total}"
    # System prompt still present.
    assert messages[0]["role"] == "system"
    # New user message still present.
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "masih muat ga?"
