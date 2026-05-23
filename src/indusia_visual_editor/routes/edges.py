"""Edge registry routes (Phase 11.1 + Phase 11.3).

POST   /api/edges            — register a new edge node
GET    /api/edges            — list all registered edges
PUT    /api/edges/{id}       — update version_policy
PUT    /api/edges/{id}/pin   — manual rollback / unpin
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from indusia_visual_editor.db.models import Edge
from indusia_visual_editor.db.session import get_session
from indusia_visual_editor.schemas.edges import (
    EdgeCreate,
    EdgePin,
    EdgeRead,
    EdgeUpdate,
)
from indusia_visual_editor.utils.responses import success


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/edges", tags=["edges"])


def _serialize(row: Edge) -> dict[str, Any]:
    return EdgeRead.model_validate(row).model_dump(mode="json")


@router.post("", status_code=status.HTTP_201_CREATED)
async def register_edge(
    body: EdgeCreate,
    session: AsyncSession = Depends(get_session),
):
    row = Edge(
        name=body.name,
        webhook_url=str(body.webhook_url),
        version_policy=body.version_policy or {"mode": "auto_pull_latest"},
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail=f"edge name {body.name!r} already registered"
        )
    await session.refresh(row)
    return success(
        data=_serialize(row),
        message="edge registered",
        status_code=status.HTTP_201_CREATED,
    )


@router.get("")
async def list_edges(session: AsyncSession = Depends(get_session)):
    rows = (
        await session.execute(select(Edge).order_by(Edge.registered_at))
    ).scalars().all()
    return success(data=[_serialize(r) for r in rows])


@router.put("/{edge_id}")
async def update_edge_policy(
    edge_id: uuid.UUID,
    body: EdgeUpdate,
    session: AsyncSession = Depends(get_session),
):
    row = await session.get(Edge, edge_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"edge {edge_id} not found")
    row.version_policy = body.version_policy
    await session.flush()
    await session.refresh(row)
    return success(data=_serialize(row))


@router.put("/{edge_id}/pin")
async def pin_edge_version(
    edge_id: uuid.UUID,
    body: EdgePin,
    session: AsyncSession = Depends(get_session),
):
    """Phase 11.3 — manual rollback / unpin.

    Both `model_name` and `version` supplied → pinned mode.
    Both absent → unpin (reset to auto_pull_latest).
    One but not both → 422.
    """
    row = await session.get(Edge, edge_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"edge {edge_id} not found")

    has_name = body.model_name is not None
    has_version = body.version is not None
    if has_name != has_version:
        raise HTTPException(
            status_code=422,
            detail=(
                "must supply both `model_name` AND `version` to pin, or "
                "neither to unpin"
            ),
        )

    if has_name and has_version:
        row.version_policy = {
            "mode": "pinned",
            "model_name": body.model_name,
            "version": body.version,
        }
    else:
        row.version_policy = {"mode": "auto_pull_latest"}

    await session.flush()
    await session.refresh(row)
    return success(data=_serialize(row))
