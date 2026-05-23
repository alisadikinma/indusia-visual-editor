"""Chat advisor routes (Phase 12.1 history APIs).

POST   /api/projects/{id}/chat   — create a new chat session
GET    /api/projects/{id}/chat   — list sessions for a project
GET    /api/chat/{session_id}    — full message list for one session

The streaming SSE endpoint lives in Phase 12.3.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from indusia_visual_editor.db.models import ChatSession, Project
from indusia_visual_editor.db.session import get_session
from indusia_visual_editor.schemas.chat import ChatSessionRead
from indusia_visual_editor.utils.responses import success


logger = logging.getLogger(__name__)


router = APIRouter(tags=["chat"])


def _serialize(row: ChatSession) -> dict[str, Any]:
    return ChatSessionRead.model_validate(row).model_dump(mode="json")


@router.post(
    "/api/projects/{project_id}/chat",
    status_code=status.HTTP_201_CREATED,
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
