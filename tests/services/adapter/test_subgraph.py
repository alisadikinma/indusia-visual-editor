"""Phase 4.2 — per-component subgraph builder.

`build_component_subgraph` emits the `{nodes, edges}` shape per
docs/specs/graphflow-config-schema.md §2 — one subgraph per inspected
BOM designator. Detectors fan out from a crop node and fan in to a
merge_result output.
"""

from __future__ import annotations

import pytest
import yaml

from indusia_visual_editor.services.adapter.node_map import (
    KNOWN_GRAPHFLOW_NODE_TYPES,
)
from indusia_visual_editor.services.adapter.subgraph import (
    build_component_subgraph,
)


def _node_types(subgraph: dict) -> set[str]:
    return {n["type"] for n in subgraph["nodes"].values()}


def test_build_component_subgraph_emits_valid_graphflow_subgraph_dict():
    sub = build_component_subgraph(
        designator="R1",
        detector_presets=["yolo"],
    )
    assert set(sub.keys()) == {"nodes", "edges"}
    assert "data" in sub["nodes"]
    assert "output" in sub["nodes"]
    assert sub["nodes"]["data"]["type"] == "input"
    assert sub["nodes"]["output"]["type"] == "merge_result"


def test_subgraph_includes_yolo_crop_when_no_bbox():
    sub = build_component_subgraph(
        designator="R1",
        detector_presets=["yolo"],
    )
    assert "crop" in sub["nodes"]
    assert sub["nodes"]["crop"]["type"] == "yolo_crop"
    assert sub["nodes"]["crop"]["params"]["classes"] == "R1"


def test_subgraph_includes_static_box_when_bbox_supplied():
    sub = build_component_subgraph(
        designator="C4",
        detector_presets=["yolo"],
        bbox=(0.1, 0.2, 0.3, 0.4),
    )
    assert "crop" in sub["nodes"]
    assert sub["nodes"]["crop"]["type"] == "static_box"
    assert sub["nodes"]["crop"]["params"]["bbox"] == [0.1, 0.2, 0.3, 0.4]


def test_subgraph_for_lifted_pin_contains_lifted_pin_detector():
    sub = build_component_subgraph(
        designator="J1",
        detector_presets=["lifted_pin"],
    )
    assert "lifted_pin_detector" in _node_types(sub)


def test_subgraph_for_ocr_contains_ocr_model():
    sub = build_component_subgraph(
        designator="U7",
        detector_presets=["ocr"],
    )
    assert "ocr_model" in _node_types(sub)


def test_subgraph_multi_preset_fans_detectors_in_parallel_after_crop():
    sub = build_component_subgraph(
        designator="C4",
        detector_presets=["yolo", "polarity_template"],
    )
    types = _node_types(sub)
    # At least one node from each preset's mapping must be present.
    assert "yolo_estimator" in types
    assert "template_match_classifier" in types
    # crop must precede both first-stage detectors via edges
    crop_targets = sub["edges"]["crop"]
    assert isinstance(crop_targets, list)
    # Both detector heads should be reachable from crop
    assert len(crop_targets) >= 2


def test_subgraph_empty_presets_still_has_data_and_output():
    sub = build_component_subgraph(
        designator="R1",
        detector_presets=[],
    )
    assert sub["nodes"]["data"]["type"] == "input"
    assert sub["nodes"]["output"]["type"] == "merge_result"
    # data should connect directly to output when no detectors are present
    assert sub["edges"]["data"] == ["output"] or "output" in sub["edges"].get("data", [])


def test_subgraph_yaml_roundtrip_clean():
    sub = build_component_subgraph(
        designator="R1",
        detector_presets=["yolo", "lifted_pin"],
    )
    dumped = yaml.safe_dump(sub, sort_keys=False)
    loaded = yaml.safe_load(dumped)
    assert loaded == sub


def test_subgraph_every_node_type_is_in_known_registry():
    """Defense in depth: no node leaks past the registry whitelist."""
    sub = build_component_subgraph(
        designator="R1",
        detector_presets=["yolo", "lifted_pin", "ocr", "polarity_template"],
    )
    for node in sub["nodes"].values():
        assert node["type"] in KNOWN_GRAPHFLOW_NODE_TYPES, (
            f"node type {node['type']!r} not in graphflow registry"
        )


def test_subgraph_edges_point_only_at_declared_nodes():
    """Edge invariant: every source + target must be a declared node name."""
    sub = build_component_subgraph(
        designator="R1",
        detector_presets=["yolo", "ocr"],
    )
    declared = set(sub["nodes"].keys())
    for source, targets in sub["edges"].items():
        assert source in declared, f"edge source {source!r} not declared"
        target_list = targets if isinstance(targets, list) else [targets]
        for t in target_list:
            assert t in declared, f"edge target {t!r} from {source!r} not declared"
