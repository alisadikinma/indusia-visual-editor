"""BOM items listing route.

GET /api/projects/{project_id}/bom_items → ordered list of bom_items for
the project. Items are inserted via the BOM upload route
(`POST /api/projects/{id}/assets?kind=bom`) — Phase 2.2 REPLACE strategy
means the response always reflects the latest uploaded BOM.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from indusia_visual_editor.db.models import BomItem
from indusia_visual_editor.db.session import get_session
from indusia_visual_editor.schemas.bom import BomItemRead
from indusia_visual_editor.services.project.crud import get_project
from indusia_visual_editor.utils.responses import success


router = APIRouter(prefix="/api/projects/{project_id}/bom_items", tags=["bom"])


def _serialize(item: BomItem) -> dict:
    return BomItemRead.model_validate(item).model_dump(mode="json")


@router.get("")
async def list_bom_items(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    await get_project(session, project_id)  # 404 if missing
    rows = (
        await session.execute(
            select(BomItem)
            .where(BomItem.project_id == project_id)
            .order_by(BomItem.designator)
        )
    ).scalars().all()
    return success(data=[_serialize(r) for r in rows])
