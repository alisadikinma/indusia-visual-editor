"""Phase 4.3 — top-level graphflow config composer + bundled defaults.

Emits the `{name, nodes, edges}` shape documented at
docs/specs/graphflow-config-schema.md §1 for one PCB side. The
adapter orchestrator (Phase 4.5) combines this with per-component
subgraphs (Phase 4.2) before the writer (Phase 4.4) lays it on disk.

Fiducial strategy mapping is hardcoded — the 4 alignment detector
node types are part of the auto-inspect-service registry (spike §3).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

FiducialStrategy = Literal["circle", "orb", "yolo", "threshold"]

FIDUCIAL_NODE_TYPE_BY_STRATEGY: dict[str, str] = {
    "circle": "circle_alignment_detector",
    "orb": "orb_alignment_detector",
    "yolo": "yolo_fiducial_detector",
    "threshold": "threshold_fiducial_detector",
}

# services/adapter/top_config.py -> services/adapter -> services -> indusia_visual_editor
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def build_top_config(
    *,
    pcb_name: str,
    fiducial_strategy: str,
    component_designators: list[str],
) -> dict:
    """Build the `{name, nodes, edges}` top-level config for one PCB side.

    Each designator becomes a `component-<D>` subgraph reference at
    `components/comp-<D>.yaml`. Edges: data -> fiducial -> [all
    components] -> output (merge_result).

    Raises:
        ValueError: fiducial_strategy not in the 4 supported literals.
    """
    if fiducial_strategy not in FIDUCIAL_NODE_TYPE_BY_STRATEGY:
        raise ValueError(
            f"unknown fiducial_strategy {fiducial_strategy!r}; "
            f"expected one of {sorted(FIDUCIAL_NODE_TYPE_BY_STRATEGY)}"
        )

    nodes: dict = {
        "data": {"type": "input"},
        "fiducial": {"type": FIDUCIAL_NODE_TYPE_BY_STRATEGY[fiducial_strategy]},
    }
    for d in component_designators:
        nodes[f"component-{d}"] = {
            "type": "graph",
            "path": f"components/comp-{d}.yaml",
        }
    nodes["output"] = {"type": "merge_result"}

    edges: dict = {
        "data": ["fiducial"],
        "fiducial": [f"component-{d}" for d in component_designators],
    }
    for d in component_designators:
        edges[f"component-{d}"] = ["output"]

    return {"name": pcb_name, "nodes": nodes, "edges": edges}


@lru_cache(maxsize=1)
def load_default_locations() -> dict:
    return yaml.safe_load((_DATA_DIR / "default_locations.yaml").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_default_settings() -> dict:
    return yaml.safe_load((_DATA_DIR / "default_settings.yaml").read_text(encoding="utf-8"))
