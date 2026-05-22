"""Phase 4.2 — per-component subgraph builder.

Each inspected BOM designator becomes one subgraph emitted as
`{nodes, edges}` per docs/specs/graphflow-config-schema.md §2.

Topology: `data` → `crop` → [each detector's node chain in parallel]
→ `output (merge_result)`. The crop node is `yolo_crop` (when no
bbox supplied — the upstream yolo finds the component itself) or
`static_box` (when a bbox came from the labeling canvas).

Detectors are sourced via Phase 4.1 `nodes_for_detector`. For each
preset we emit its full node chain; the first chain node receives
input from `crop`, the last node fans into `output`.
"""

from __future__ import annotations

from typing import Sequence

from indusia_visual_editor.services.adapter.node_map import nodes_for_detector


def build_component_subgraph(
    *,
    designator: str,
    detector_presets: Sequence[str],
    bbox: tuple[float, float, float, float] | None = None,
) -> dict:
    """Build the `{nodes, edges}` dict for one inspected designator.

    Args:
        designator: BOM identifier like "R1" / "U7"; used as YOLO class
            label or static_box anchor.
        detector_presets: list of preset names from Phase 2.2c's
            defect_detector_mapping.yaml; each expands via Phase 4.1.
        bbox: optional normalized (x, y, w, h) — when set, the crop
            node switches to `static_box` (use the labeled rectangle
            directly instead of YOLO-detecting the component).

    Returns:
        A dict with two top-level keys: `nodes` and `edges`, ready for
        yaml.safe_dump per graphflow §2.
    """
    nodes: dict = {"data": {"type": "input"}}

    if bbox is not None:
        nodes["crop"] = {
            "type": "static_box",
            "params": {"bbox": list(bbox)},
        }
    else:
        nodes["crop"] = {
            "type": "yolo_crop",
            "params": {"classes": designator, "expand_ratio": 0.2},
        }

    edges: dict = {"data": ["crop"] if detector_presets else ["output"]}

    # Per-preset chain: name nodes <preset>__<index> so multiple presets
    # don't collide on a shared type (e.g. two presets both ending in
    # `transform_result` would otherwise overwrite each other).
    chain_heads: list[str] = []
    chain_tails: list[str] = []

    for preset in detector_presets:
        chain_specs = nodes_for_detector(preset)
        if not chain_specs:
            continue
        chain_names: list[str] = []
        for idx, spec in enumerate(chain_specs):
            name = f"{preset}__{idx}"
            nodes[name] = {"type": spec.type}
            if spec.params:
                nodes[name]["params"] = dict(spec.params)
            chain_names.append(name)
        # Edge chain within this preset
        for src, tgt in zip(chain_names, chain_names[1:]):
            edges[src] = [tgt]
        chain_heads.append(chain_names[0])
        chain_tails.append(chain_names[-1])

    if chain_heads:
        edges["crop"] = list(chain_heads)
        for tail in chain_tails:
            edges[tail] = ["output"]

    nodes["output"] = {"type": "merge_result"}

    return {"nodes": nodes, "edges": edges}
