"""Bundle 2.0 — cross-project dashboard rollup.

Pure read-side aggregation over existing tables (projects, bom_items,
train_runs, deployments, edges). No migration, no telemetry table. Every
number traces to a real row:

  - project status counts come from `projects.status`
  - models_deployed = deployments in the `succeeded` state
  - edges_online = edges whose `last_seen_at` is within ONLINE_WINDOW
  - avg_map / per-project latest_map = mAP of the most recent succeeded
    TrainRun per project (metrics_json -> "mAP")
  - bom_count = rows in bom_items per project

Deliberately ABSENT (no backing data source — would be fabrication):
trend deltas (no historical snapshots) and the 7-day inspection chart (no
inspection-results table). The DashboardView hides those affordances rather
than render invented numbers.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from indusia_visual_editor.db.models import (
    BomItem,
    Deployment,
    Edge,
    Project,
    TrainRun,
)

# An edge counts as "online" if it pinged within this window. Edge health
# pings (M14) populate last_seen_at; until then every edge reads offline,
# which is the honest state, not a fabricated "online" flag.
ONLINE_WINDOW = timedelta(minutes=5)


async def compute_dashboard_summary(session: AsyncSession) -> dict:
    # --- project status counts ---
    status_rows = (
        await session.execute(
            select(Project.status, func.count()).group_by(Project.status)
        )
    ).all()
    status_counts: dict[str, int] = {s: int(n) for s, n in status_rows}
    drafting = status_counts.get("drafting", 0)
    training = status_counts.get("training", 0)
    deployed = status_counts.get("deployed", 0)
    failed = status_counts.get("failed", 0)
    active_projects = drafting + training + deployed

    # --- models deployed (succeeded deployments) ---
    models_deployed = int(
        (
            await session.execute(
                select(func.count()).select_from(Deployment).where(
                    Deployment.status == "succeeded"
                )
            )
        ).scalar_one()
    )

    # --- edges online / total ---
    edges_total = int(
        (await session.execute(select(func.count()).select_from(Edge))).scalar_one()
    )
    cutoff = datetime.now(timezone.utc) - ONLINE_WINDOW
    edges_online = int(
        (
            await session.execute(
                select(func.count())
                .select_from(Edge)
                .where(Edge.last_seen_at.is_not(None), Edge.last_seen_at >= cutoff)
            )
        ).scalar_one()
    )

    # --- BOM counts per project ---
    bom_rows = (
        await session.execute(
            select(BomItem.project_id, func.count()).group_by(BomItem.project_id)
        )
    ).all()
    bom_by_project: dict[str, int] = {str(pid): int(n) for pid, n in bom_rows}

    # --- latest succeeded mAP per project ---
    # Order by ended_at then started_at so the most recent terminal run wins.
    latest_map_by_project: dict[str, float] = {}
    map_rows = (
        await session.execute(
            select(
                TrainRun.project_id,
                TrainRun.metrics_json,
                TrainRun.started_at,
                TrainRun.ended_at,
            ).where(TrainRun.status == "succeeded")
        )
    ).all()
    seen_order: dict[str, datetime] = {}
    for pid, metrics, started, ended in map_rows:
        if not metrics or "mAP" not in metrics:
            continue
        ts = ended or started
        key = str(pid)
        if key not in seen_order or (ts is not None and ts > seen_order[key]):
            seen_order[key] = ts
            try:
                latest_map_by_project[key] = float(metrics["mAP"])
            except (TypeError, ValueError):
                continue

    avg_map = (
        round(sum(latest_map_by_project.values()) / len(latest_map_by_project), 4)
        if latest_map_by_project
        else None
    )

    # --- per-project rows (most-recently-updated first) ---
    projects = (
        (
            await session.execute(
                select(Project).order_by(Project.updated_at.desc())
            )
        )
        .scalars()
        .all()
    )
    project_rows = [
        {
            "id": str(p.id),
            "name": p.name,
            "slug": p.slug,
            "status": p.status,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            "bom_count": bom_by_project.get(str(p.id), 0),
            "latest_map": latest_map_by_project.get(str(p.id)),
        }
        for p in projects
    ]

    return {
        "stats": {
            "active_projects": active_projects,
            "drafting": drafting,
            "training": training,
            "deployed": deployed,
            "failed": failed,
            "models_deployed": models_deployed,
            "edges_online": edges_online,
            "edges_total": edges_total,
            "avg_map": avg_map,
        },
        "projects": project_rows,
    }
