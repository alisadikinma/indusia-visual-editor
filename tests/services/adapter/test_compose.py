"""Phase 4.5 — adapter orchestrator.

`compose_from_project` is the one place that joins:
  - latest ProposedPipeline row (Phase 3.4) for pcb_name + fiducial_strategy
  - bom_items table (Phase 1.1) for designator inventory
  - LSF annotation parsed via derive_inspect_scope (Phase 2.2c)
  - per-component subgraph builder (Phase 4.2)
  - top-level config + defaults (Phase 4.3)
  - atomic writer (Phase 4.4)

Tests assert: skipped regions excluded, missing plan → NoPlanError,
all-skipped → NoInspectedRegionsError, model dir landed on disk with
correct components inside.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
import yaml
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from indusia_visual_editor.db.models import (
    BomItem,
    InspectScope,
    Project,
    ProposedPipelineRow,
)
from indusia_visual_editor.services.adapter.compose import (
    NoInspectedRegionsError,
    NoPlanError,
    compose_from_project,
)
from indusia_visual_editor.services.inspect_scope.derive import LSAnnotation


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


async def _seed_project(
    session: AsyncSession, *, slug_suffix: str, pcb_name: str = "NV80"
) -> uuid.UUID:
    p = Project(name=f"compose-{slug_suffix}", slug=f"compose-{slug_suffix}-{uuid.uuid4().hex[:6]}")
    session.add(p)
    await session.flush()
    return p.id


async def _seed_bom(session: AsyncSession, project_id: uuid.UUID, designators: list[str]) -> None:
    for d in designators:
        session.add(BomItem(project_id=project_id, designator=d))
    await session.flush()


async def _seed_plan(
    session: AsyncSession, project_id: uuid.UUID, *, pcb_name: str = "NV80"
) -> None:
    plan = {
        "pcb_model": pcb_name,
        "fiducial_strategy": "circle",
        "steps": [],
    }
    session.add(
        ProposedPipelineRow(project_id=project_id, version=1, dag_json=plan)
    )
    await session.flush()


def _annotation_for(designator: str, scope: str = "inspected", criteria: list[str] | None = None) -> dict:
    region_id = f"r-{designator}"
    return {
        "id": region_id,
        "type": "rectanglelabels",
        "from_name": "component",
        "to_name": "image",
        "value": {"rectanglelabels": [designator]},
    }, {
        "id": region_id,
        "type": "choices",
        "from_name": "inspect_scope",
        "to_name": "image",
        "value": {"choices": [scope]},
    }, {
        "id": region_id,
        "type": "choices",
        "from_name": "scope_mode",
        "to_name": "image",
        "value": {"choices": ["per_component"]},
    }, {
        "id": region_id,
        "type": "choices",
        "from_name": "defect_criteria",
        "to_name": "image",
        "value": {"choices": criteria or []},
    } if (criteria is not None) else None


def _build_annotation(rows: list[tuple[str, str, list[str]]]) -> LSAnnotation:
    """rows: list of (designator, scope, criteria) — empty list = unspecified."""
    result: list[dict] = []
    for designator, scope, criteria in rows:
        region_id = f"r-{designator}"
        result.append(
            {
                "id": region_id, "type": "rectanglelabels",
                "from_name": "component", "to_name": "image",
                "value": {"rectanglelabels": [designator]},
            }
        )
        result.append(
            {
                "id": region_id, "type": "choices",
                "from_name": "inspect_scope", "to_name": "image",
                "value": {"choices": [scope]},
            }
        )
        result.append(
            {
                "id": region_id, "type": "choices",
                "from_name": "scope_mode", "to_name": "image",
                "value": {"choices": ["per_component"]},
            }
        )
        if criteria:
            result.append(
                {
                    "id": region_id, "type": "choices",
                    "from_name": "defect_criteria", "to_name": "image",
                    "value": {"choices": criteria},
                }
            )
    return LSAnnotation(result=result)


@pytest.mark.asyncio
async def test_compose_from_project_writes_full_tree_from_db_state(
    db_session: AsyncSession, tmp_path: Path
):
    pid = await _seed_project(db_session, slug_suffix="happy")
    await _seed_bom(db_session, pid, ["R1", "C4"])
    await _seed_plan(db_session, pid)
    await db_session.commit()

    annotation = _build_annotation(
        [
            ("R1", "inspected", ["missing_component"]),
            ("C4", "skipped", []),
        ]
    )

    result = await compose_from_project(
        session=db_session,
        project_id=pid,
        lsf_annotation=annotation,
        models_root=tmp_path,
    )

    pcb_dir = tmp_path / "NV80"
    assert pcb_dir.is_dir()
    assert (pcb_dir / "config.yaml").is_file()
    assert (pcb_dir / "locations.yaml").is_file()
    assert (pcb_dir / "settings.yaml").is_file()
    # R1 was inspected, must have a subgraph
    assert (pcb_dir / "components" / "comp-R1.yaml").is_file()
    # C4 was skipped, must NOT have one
    assert not (pcb_dir / "components" / "comp-C4.yaml").is_file()

    top = yaml.safe_load((pcb_dir / "config.yaml").read_text(encoding="utf-8"))
    assert top["name"] == "NV80"
    assert top["nodes"]["fiducial"]["type"] == "circle_alignment_detector"
    assert "component-R1" in top["nodes"]
    assert "component-C4" not in top["nodes"]

    assert result.pcb_name == "NV80"
    assert result.inspected_count == 1
    assert result.model_dir == pcb_dir.resolve()


@pytest.mark.asyncio
async def test_compose_from_project_raises_when_no_plan(
    db_session: AsyncSession, tmp_path: Path
):
    pid = await _seed_project(db_session, slug_suffix="noplan")
    await _seed_bom(db_session, pid, ["R1"])
    await db_session.commit()  # no plan inserted

    annotation = _build_annotation([("R1", "inspected", ["missing_component"])])

    with pytest.raises(NoPlanError):
        await compose_from_project(
            session=db_session,
            project_id=pid,
            lsf_annotation=annotation,
            models_root=tmp_path,
        )
    # No model dir created
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_compose_from_project_raises_when_all_skipped(
    db_session: AsyncSession, tmp_path: Path
):
    pid = await _seed_project(db_session, slug_suffix="allskip")
    await _seed_bom(db_session, pid, ["R1", "C4"])
    await _seed_plan(db_session, pid)
    await db_session.commit()

    annotation = _build_annotation(
        [
            ("R1", "skipped", []),
            ("C4", "skipped", []),
        ]
    )

    with pytest.raises(NoInspectedRegionsError):
        await compose_from_project(
            session=db_session,
            project_id=pid,
            lsf_annotation=annotation,
            models_root=tmp_path,
        )
    assert list(tmp_path.iterdir()) == []
