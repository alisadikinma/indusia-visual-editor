"""Phase 4.1 - detector preset to graphflow node-set mapping.

Locks the v1 vocabulary per spike section 6.1. Each detector preset
from data/defect_detector_mapping.yaml expands to an ordered list of
NodeSpec entries the subgraph builder (Phase 4.2) will consume.
"""

import pytest

from indusia_visual_editor.services.adapter.node_map import (
    KNOWN_GRAPHFLOW_NODE_TYPES,
    NodeSpec,
    UnknownDetectorPreset,
    nodes_for_detector,
)

# The 13 detector preset names locked in this phase. Mirror of the
# distinct values in data/defect_detector_mapping.yaml (Phase 2.2c)
# plus barcode + template_match reserved for future criteria.
ALL_PRESETS = [
    "yolo",
    "yolo_fine_grained",
    "anomalib_roi",
    "anomalib_whole_side",
    "ocr",
    "barcode",
    "template_match",
    "polarity_template",
    "orientation_classifier",
    "lifted_pin",
    "pin_count_check",
    "border_alignment",
    "threshold",
]


def test_nodes_for_detector_yolo_returns_yolo_estimator_then_transform():
    nodes = nodes_for_detector("yolo")
    assert len(nodes) >= 2
    assert all(isinstance(n, NodeSpec) for n in nodes)
    types = [n.type for n in nodes]
    assert "yolo_estimator" in types
    assert any(t.startswith("transform_") for t in types)


def test_nodes_for_detector_yolo_fine_grained_sets_verbose_and_expand_ratio():
    nodes = nodes_for_detector("yolo_fine_grained")
    types = [n.type for n in nodes]
    assert "yolo_estimator" in types
    yolo_node = next(n for n in nodes if n.type == "yolo_estimator")
    assert yolo_node.params is not None
    assert yolo_node.params.get("verbose") is True
    assert "expand_ratio" in yolo_node.params


def test_nodes_for_detector_lifted_pin_contains_lifted_pin_detector():
    nodes = nodes_for_detector("lifted_pin")
    types = [n.type for n in nodes]
    assert "lifted_pin_detector" in types
    assert any(t.startswith("transform_") for t in types)


def test_nodes_for_detector_ocr_contains_ocr_model_and_ocr_transform():
    nodes = nodes_for_detector("ocr")
    types = [n.type for n in nodes]
    assert "ocr_model" in types
    assert "transform_ocr_result" in types


def test_nodes_for_detector_polarity_template_uses_template_match_classifier():
    nodes = nodes_for_detector("polarity_template")
    types = [n.type for n in nodes]
    assert "template_match_classifier" in types


def test_nodes_for_detector_anomalib_whole_side_uses_dino_predictor():
    nodes = nodes_for_detector("anomalib_whole_side")
    types = [n.type for n in nodes]
    assert "anomaly_dino_predictor" in types
    assert "anomaly_result" in types


def test_nodes_for_detector_anomalib_roi_has_decision_step():
    nodes = nodes_for_detector("anomalib_roi")
    types = [n.type for n in nodes]
    assert "anomaly_predictor" in types
    assert "anomaly_decision" in types
    assert "anomaly_result" in types


def test_nodes_for_detector_barcode_uses_barcode_detector():
    nodes = nodes_for_detector("barcode")
    types = [n.type for n in nodes]
    assert "barcode_detector" in types
    assert "transform_barcode_result" in types


def test_nodes_for_detector_unknown_preset_raises_typed_exception():
    with pytest.raises(UnknownDetectorPreset):
        nodes_for_detector("does_not_exist_42")


def test_nodes_for_detector_empty_string_raises_typed_exception():
    with pytest.raises(UnknownDetectorPreset):
        nodes_for_detector("")


def test_nodespec_rejects_unknown_node_type():
    with pytest.raises(ValueError):
        NodeSpec(type="totally_made_up_node", params=None)


def test_every_emitted_node_type_is_in_registry():
    """Meta-test: prevents drift from the 49-name registry."""
    for preset in ALL_PRESETS:
        nodes = nodes_for_detector(preset)
        assert len(nodes) >= 1, f"preset {preset} produced empty node list"
        for node in nodes:
            assert node.type in KNOWN_GRAPHFLOW_NODE_TYPES, (
                f"preset {preset} emitted unknown type {node.type!r}"
            )


def test_known_graphflow_node_types_registry_is_complete():
    """Mirror of docs/specs/graphflow-config-schema.md section 3 enumeration.

    The spec header states '49 types' but the enumeration table itself
    lists 51 distinct names (Structural 5 + Anomaly 5 + YOLO 5 +
    Fiducial 6 + Detectors 10 + Cropping 2 + OCR/barcode 3 +
    Transforms 9 + Merge 6). We mirror the enumeration, not the header.
    """
    assert len(KNOWN_GRAPHFLOW_NODE_TYPES) == 51
    # Spot-check representatives from each category to catch typos.
    for required in (
        "input",
        "graph",
        "merge_result",
        "yolo_estimator",
        "yolo_crop",
        "anomaly_dino_predictor",
        "lifted_pin_detector",
        "border_alignment_detector",
        "orientation_classifier",
        "ocr_model",
        "barcode_detector",
        "template_match_classifier",
        "transform_result",
        "transform_ocr_result",
        "transform_barcode_result",
    ):
        assert required in KNOWN_GRAPHFLOW_NODE_TYPES
