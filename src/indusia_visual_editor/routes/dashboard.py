"""Bundle 2.0 — GET /api/dashboard/summary.

Read-only cross-project rollup for the redesigned DashboardView. Public GET
(matches the v1 decision that GETs stay open; see CLAUDE.md §16). All numbers
trace to real rows — see services/dashboard/summary for the contract and the
deliberately-absent trend/chart fields.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from indusia_visual_editor.db.session import get_session
from indusia_visual_editor.services.dashboard.summary import compute_dashboard_summary
from indusia_visual_editor.utils.responses import success


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
async def get_dashboard_summary(session: AsyncSession = Depends(get_session)):
    data = await compute_dashboard_summary(session)
    return success(data=data)
