"""Request/response schemas for the chat advisor (Phase 12.1+)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    """One turn in a chat session.

    The streaming SSE endpoint (Phase 12.3) appends user and assistant
    turns to `chat_sessions.messages_json` after each round trip; the
    Gemma context builder (Phase 12.2) reads them in order to feed the
    last N turns back as conversation history.
    """

    role: Literal["user", "assistant", "system"]
    content: str
    ts: datetime


class ChatSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    messages_json: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class ChatStreamRequest(BaseModel):
    """Body of `POST /api/chat/{session_id}/stream` (Phase 12.3)."""

    user_message: str = Field(min_length=1)
