"""Chat advisor routes (Phase 12.1 history APIs + Phase 12.3 streaming).

POST   /api/projects/{id}/chat            — create a new chat session
GET    /api/projects/{id}/chat            — list sessions for a project
GET    /api/chat/{session_id}             — full message list for one session
POST   /api/chat/{session_id}/stream      — SSE stream Gemma advisor response

The streaming endpoint appends the user turn before opening the upstream
chat stream, relays each delta to the SSE caller, and on terminal append
the assembled assistant turn to chat_sessions.messages_json. The user
turn is persisted up-front so an upstream transport failure still leaves
a clean audit trail of what the operator asked.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from indusia_visual_editor.config import get_config
from indusia_visual_editor.db.models import ChatSession, Project
from indusia_visual_editor.db.session import get_session, get_sessionmaker
from indusia_visual_editor.schemas.chat import ChatSessionRead, ChatStreamRequest
from indusia_visual_editor.services.auth.dependencies import get_current_user
from indusia_visual_editor.services.llm.chat import build_chat_context
from indusia_visual_editor.services.llm.client import OllamaClient
from indusia_visual_editor.services.llm.exceptions import (
    LlmConnectionError,
    LlmResponseError,
    LlmTimeoutError,
)
from indusia_visual_editor.utils.responses import success


logger = logging.getLogger(__name__)


router = APIRouter(tags=["chat"])


# Test seam — same pattern as routes/llm.py. Tests override via
# set_llm_client_factory() with a fake that emits scripted chunks.
_llm_client_factory = OllamaClient


def set_llm_client_factory(factory) -> None:
    """Test-only seam to inject a fake OllamaClient."""
    global _llm_client_factory
    _llm_client_factory = factory


def reset_llm_client_factory() -> None:
    global _llm_client_factory
    _llm_client_factory = OllamaClient


def _serialize(row: ChatSession) -> dict[str, Any]:
    return ChatSessionRead.model_validate(row).model_dump(mode="json")


@router.post(
    "/api/projects/{project_id}/chat",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_user)],
)
async def create_chat_session(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"project {project_id} not found")

    row = ChatSession(project_id=project_id, messages_json=[])
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return success(
        data=_serialize(row),
        message="chat session created",
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/api/projects/{project_id}/chat")
async def list_chat_sessions(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"project {project_id} not found")

    rows = (
        await session.execute(
            select(ChatSession)
            .where(ChatSession.project_id == project_id)
            .order_by(ChatSession.created_at)
        )
    ).scalars().all()
    return success(data=[_serialize(r) for r in rows])


@router.get("/api/chat/{session_id}")
async def get_chat_session(
    session_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    row = await session.get(ChatSession, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"chat session {session_id} not found")
    return success(data=_serialize(row))


# ---------------- Phase 12.3 — streaming SSE ----------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _append_turn(
    session_id: uuid.UUID, role: str, content: str
) -> None:
    """Append one turn to chat_sessions.messages_json in a short-lived
    session. The EventSourceResponse generator outlives the request-scoped
    dep session, so we own a fresh session per write."""
    factory = get_sessionmaker()
    async with factory() as s:
        row = await s.get(ChatSession, session_id)
        if row is None:
            return
        turns = list(row.messages_json or [])
        turns.append({"role": role, "content": content, "ts": _now_iso()})
        # Reassign to trigger JSONB column dirty-tracking on PostgreSQL.
        row.messages_json = turns
        await s.commit()


@router.post(
    "/api/chat/{session_id}/stream",
    dependencies=[Depends(get_current_user)],
)
async def stream_chat_reply(
    session_id: uuid.UUID,
    body: ChatStreamRequest,
    session: AsyncSession = Depends(get_session),
):
    """Stream Gemma advisor response as SSE.

    Wire format: each upstream chunk is emitted as one `data:` line whose
    payload is a JSON object `{"delta": "<chunk text>"}`. The terminal
    line is `{"event": "done"}`. Errors during streaming are emitted as
    `{"event": "error", "error": "<message>"}` and the row's assistant
    turn captures whatever was assembled before the failure.
    """
    chat = await session.get(ChatSession, session_id)
    if chat is None:
        raise HTTPException(
            status_code=404, detail=f"chat session {session_id} not found"
        )
    project_id = chat.project_id

    # Build context FIRST against the clean pre-turn history — the builder
    # adds `user_message` as the final user message itself, so we let the
    # row's messages_json hold only prior turns at this point. After the
    # context is materialized, we persist the user turn (so an upstream
    # transport failure still leaves a clean audit trail of what the
    # operator asked).
    messages = await build_chat_context(
        session,
        project_id=project_id,
        session_id=session_id,
        user_message=body.user_message,
    )
    await _append_turn(session_id, "user", body.user_message)

    cfg = get_config()

    async def event_generator():
        client = _llm_client_factory(
            base_url=cfg.ollama_url, timeout=cfg.ollama_timeout
        )
        assembled_parts: list[str] = []
        try:
            try:
                async for chunk in client.stream_chat(
                    model=cfg.ollama_model_planner, messages=messages
                ):
                    assembled_parts.append(chunk)
                    yield {"data": json.dumps({"delta": chunk})}
            except (LlmConnectionError, LlmTimeoutError, LlmResponseError) as exc:
                logger.warning(
                    "chat stream upstream error for session %s: %s", session_id, exc
                )
                yield {"data": json.dumps({"event": "error", "error": str(exc)})}
            else:
                yield {"data": json.dumps({"event": "done"})}
        finally:
            assistant_text = "".join(assembled_parts)
            if assistant_text:
                await _append_turn(session_id, "assistant", assistant_text)
            try:
                await client.aclose()
            except Exception:
                pass

    return EventSourceResponse(event_generator())
