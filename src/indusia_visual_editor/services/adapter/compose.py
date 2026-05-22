"""Phase 4.5 — adapter orchestrator.

`compose_from_project` is the one place that joins all the M4 pieces:

  - Phase 3.4: latest ProposedPipelineRow → `pcb_name` + `fiducial_strategy`
  - Phase 1.1: bom_items table — designator inventory (for sanity)
  - Phase 2.2c: derive_inspect_scope(LSF annotation) → BomItemUpdate list
                with `detector_presets` already resolved
  - Phase 4.2: build_component_subgraph per inspected designator
  - Phase 4.3: build_top_config + default locations/settings
  - Phase 4.4: write_model_dir atomic on-disk layout

Skipped regions are excluded from the output tree. Two failure modes
are typed so the route layer (Phase 4.6) can map each to a 422:
  - NoPlanError       — no ProposedPipelineRow exists yet
  - NoInspectedRegionsError — annotation has zero inspected regions
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from indusia_visual_editor.db.models import ProposedPipelineRow
from indusia_visual_editor.services.adapter.subgraph import (
    build_component_subgraph,
)
from indusia_visual_editor.services.adapter.top_config import (
    build_top_config,
    load_default_locations,
    load_default_settings,
)
from indusia_visual_editor.services.adapter.writer import write_model_dir
from indusia_visual_editor.services.inspect_scope.derive import (
    LSAnnotation,
    derive_inspect_scope,
)


class NoPlanError(ValueError):
    """Raised when the project has no `proposed_pipelines` row yet."""


class NoInspectedRegionsError(ValueError):
    """Raised when the LSF annotation has zero inspected regions —
    nothing to emit a model dir for."""


@dataclass(frozen=True)
class ComposeResult:
    model_dir: Path
    inspected_count: int
    pcb_name: str


async def compose_from_project(
    *,
    session: AsyncSession,
    project_id: uuid.UUID,
    lsf_annotation: LSAnnotation,
    models_root: Path,
) -> ComposeResult:
    """Compose the graphflow model dir for a project from its current state.

    Returns:
        ComposeResult with the absolute model_dir path, inspected count,
        and the pcb_name (= directory name).

    Raises:
        NoPlanError: project has no proposed_pipelines row yet — caller
            must invoke `/api/projects/{id}/llm/plan` first.
        NoInspectedRegionsError: every region in the annotation is
            scope=skipped — there's nothing to inspect.
    """
    plan_row = (
        await session.execute(
            select(ProposedPipelineRow)
            .where(ProposedPipelineRow.project_id == project_id)
            .order_by(desc(ProposedPipelineRow.version))
            .limit(1)
        )
    ).scalar_one_or_none()
    if plan_row is None:
        raise NoPlanError(
            f"project {project_id} has no ProposedPipelineRow; "
            "POST /api/projects/{id}/llm/plan first"
        )

    dag = plan_row.dag_json or {}
    pcb_name = str(dag.get("pcb_model") or "unknown")
    fiducial_strategy = str(dag.get("fiducial_strategy") or "circle")

    updates = derive_inspect_scope(lsf_annotation)
    inspected = [u for u in updates if u.inspect_scope == "inspected"]
    if not inspected:
        raise NoInspectedRegionsError(
            f"project {project_id} annotation has zero inspected regions"
        )

    subgraphs: dict[str, dict] = {
        u.designator: build_component_subgraph(
            designator=u.designator,
            detector_presets=u.detector_presets,
        )
        for u in inspected
    }
    top_config = build_top_config(
        pcb_name=pcb_name,
        fiducial_strategy=fiducial_strategy,
        component_designators=list(subgraphs.keys()),
    )
    locations = load_default_locations()
    settings = load_default_settings()

    model_dir = write_model_dir(
        target_root=models_root,
        pcb_name=pcb_name,
        top_config=top_config,
        locations=locations,
        settings=settings,
        subgraphs=subgraphs,
    )

    return ComposeResult(
        model_dir=model_dir,
        inspected_count=len(inspected),
        pcb_name=pcb_name,
    )
