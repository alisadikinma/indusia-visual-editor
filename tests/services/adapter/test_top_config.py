"""Phase 4.3 — top-level config.yaml + default locations + settings.

build_top_config wires the alignment stage + per-component subgraph
refs + merge output for one PCB side. locations + settings defaults
ship as bundled YAML and are loaded via helpers; M6 spatial
calibration / M14 polish refine them later.
"""

import pytest
import yaml

from indusia_visual_editor.services.adapter.top_config import (
    FIDUCIAL_NODE_TYPE_BY_STRATEGY,
    build_top_config,
    load_default_locations,
    load_default_settings,
)


def test_build_top_config_wires_fiducial_then_subgraphs_then_merge():
    cfg = build_top_config(
        pcb_name="NV80",
        fiducial_strategy="circle",
        component_designators=["R1", "C4", "U7"],
    )
    assert cfg["name"] == "NV80"
    nodes = cfg["nodes"]
    assert nodes["data"]["type"] == "input"
    assert nodes["fiducial"]["type"] == "circle_alignment_detector"
    assert nodes["component-R1"]["type"] == "graph"
    assert nodes["component-R1"]["path"] == "components/comp-R1.yaml"
    assert nodes["component-C4"]["path"] == "components/comp-C4.yaml"
    assert nodes["component-U7"]["path"] == "components/comp-U7.yaml"
    assert nodes["output"]["type"] == "merge_result"
    edges = cfg["edges"]
    assert edges["data"] == ["fiducial"]
    assert set(edges["fiducial"]) == {"component-R1", "component-C4", "component-U7"}
    assert edges["component-R1"] == ["output"]


@pytest.mark.parametrize(
    "strategy,expected_type",
    [
        ("circle", "circle_alignment_detector"),
        ("orb", "orb_alignment_detector"),
        ("yolo", "yolo_fiducial_detector"),
        ("threshold", "threshold_fiducial_detector"),
    ],
)
def test_build_top_config_maps_each_fiducial_strategy_to_correct_node_type(strategy, expected_type):
    cfg = build_top_config(
        pcb_name="X",
        fiducial_strategy=strategy,
        component_designators=["R1"],
    )
    assert cfg["nodes"]["fiducial"]["type"] == expected_type


def test_build_top_config_rejects_unknown_fiducial_strategy():
    with pytest.raises(ValueError):
        build_top_config(
            pcb_name="X",
            fiducial_strategy="magic",
            component_designators=["R1"],
        )


def test_build_top_config_yaml_roundtrip_preserves_shape():
    cfg = build_top_config(
        pcb_name="NV80",
        fiducial_strategy="orb",
        component_designators=["R1", "C4"],
    )
    dumped = yaml.safe_dump(cfg)
    loaded = yaml.safe_load(dumped)
    assert loaded == cfg
    assert FIDUCIAL_NODE_TYPE_BY_STRATEGY["orb"] == "orb_alignment_detector"


def test_default_locations_has_top_and_bottom_frames():
    loc = load_default_locations()
    frames = loc["frames"]
    sides = {f["side"] for f in frames}
    assert sides == {"top", "bottom"}
    for f in frames:
        assert "frame_id" in f
        assert "location" in f
        assert "unit" in f


def test_default_settings_has_camera_and_lighting_blocks():
    s = load_default_settings()
    assert "camera" in s
    assert "lighting" in s
