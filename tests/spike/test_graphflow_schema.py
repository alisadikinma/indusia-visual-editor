"""Phase 0.2 spike: prove we understand the auto-inspect-service graphflow schema.

The M4 planner adapter must emit YAML that this service accepts. Before
designing the adapter, we need authoritative knowledge of the schema. These
tests load two hand-rendered fixtures (one top-level, one subgraph) modelled
after the real conventions documented in
`auto-inspect-service/README.md` §2 and the preset library at
`src/auto_inspect_service/templates/presets/*.yaml`.

The upstream presets contain Jinja2 templates (`{{var|default}}`) and are not
parseable as raw YAML, so we ship the rendered fixtures under fixtures/ and
document the rendering convention in docs/specs/graphflow-config-schema.md.

The KNOWN_NODE_TYPES set below is the full registry observed in
`src/auto_inspect_service/schemas/node_params.yaml`. M4 planner output MUST
restrict itself to these types.
"""

from pathlib import Path

import yaml

FIXTURES_DIR = Path(__file__).parent / "fixtures"
TOP_LEVEL_FIXTURE = FIXTURES_DIR / "top_level_config_rendered.yaml"
SUBGRAPH_FIXTURE = FIXTURES_DIR / "missing_yolo_rendered.yaml"

# Full registry from auto-inspect-service/src/auto_inspect_service/schemas/node_params.yaml
# (49 entries observed 2026-05-22). Plus `graph` which is a structural reference
# (subgraph include) used at the top level only.
KNOWN_NODE_TYPES = {
    # Structural
    "input", "graph", "script", "switch", "rejected",
    # Anomaly
    "anomaly_predictor", "anomaly_dino_predictor", "anomaly_imgproc_predictor",
    "anomaly_decision", "anomaly_result",
    # YOLO family
    "yolo_estimator", "yolo_anomaly_predictor", "yolo_crop",
    "yolo_fiducial_detector", "yolo_lifted_pin_detector",
    # Fiducial / alignment
    "fiducial_detector", "fiducial_detector_v2",
    "orb_alignment_detector", "circle_alignment_detector",
    "threshold_fiducial_detector", "border_alignment_detector",
    # Detectors
    "template_match_detector", "template_match_classifier",
    "golden_reference", "orientation_classifier",
    "threshold_detector", "bright_region_detector", "bright_region_crop",
    "bright_region_split", "light_background_detector",
    "lifted_pin_detector",
    # Cropping
    "tile_crop", "threshold_crop",
    # OCR / barcode
    "ocr_model", "data_matrix_detector", "barcode_detector",
    # Transforms
    "transform_result", "transform_anomaly_result", "transform_box_result",
    "transform_probs_result", "transform_single_result", "transform_ocr_result",
    "transform_barcode_result", "transform_data_matrix_result",
    "transform_light_background_result",
    # Merge / output / debug
    "merge_result", "merge_tile_result",
    "check_missing", "static_box", "show_image", "save_image",
}


def _assert_valid_dag(cfg: dict) -> None:
    """Shared structural invariants — nodes is a dict of name→{type,...},
    edges is a dict of source_node→(node OR list[node]), all referenced names
    must be declared in nodes."""
    assert isinstance(cfg["nodes"], dict)
    for node_name, node_def in cfg["nodes"].items():
        assert isinstance(node_def, dict), f"node {node_name!r} not a mapping"
        assert "type" in node_def, f"node {node_name!r} missing 'type'"
        assert isinstance(node_def["type"], str)
        assert node_def["type"] in KNOWN_NODE_TYPES, (
            f"node {node_name!r} uses unknown type {node_def['type']!r}"
        )

    node_names = set(cfg["nodes"].keys())
    assert isinstance(cfg["edges"], dict)
    for src, targets in cfg["edges"].items():
        assert src in node_names, f"edge source {src!r} not declared in nodes"
        target_list = targets if isinstance(targets, list) else [targets]
        for t in target_list:
            assert t in node_names, f"edge target {t!r} not declared in nodes"


def test_top_level_config_has_name_nodes_edges():
    """Top-level pipeline config (passed to POST /api/models/{name}/load).
    Has exactly {name, nodes, edges} at the root. Uses `type: graph` + `path:`
    to reference per-component subgraph yamls."""
    assert TOP_LEVEL_FIXTURE.exists(), f"fixture missing: {TOP_LEVEL_FIXTURE}"
    with TOP_LEVEL_FIXTURE.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    assert set(cfg.keys()) == {"name", "nodes", "edges"}, (
        f"unexpected top-level keys: {set(cfg.keys())}"
    )
    assert isinstance(cfg["name"], str) and cfg["name"], "name must be non-empty string"

    _assert_valid_dag(cfg)

    types = {n["type"] for n in cfg["nodes"].values()}
    assert "input" in types, "every pipeline must declare an input node"

    # Top-level config references subgraphs via type=graph + path=<relative>.
    graph_nodes = [n for n in cfg["nodes"].values() if n["type"] == "graph"]
    assert graph_nodes, "top-level config expected to reference at least one subgraph"
    for gn in graph_nodes:
        assert "path" in gn, "graph reference node must carry a 'path' string"
        assert gn["path"].endswith(".yaml")


def test_subgraph_config_has_only_nodes_and_edges():
    """Per-component subgraph (referenced from top-level via type=graph + path).
    Has only {nodes, edges}; no `name` field (identifier comes from the parent's
    node label)."""
    assert SUBGRAPH_FIXTURE.exists(), f"fixture missing: {SUBGRAPH_FIXTURE}"
    with SUBGRAPH_FIXTURE.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    assert set(cfg.keys()) == {"nodes", "edges"}, (
        f"unexpected subgraph keys: {set(cfg.keys())}"
    )
    _assert_valid_dag(cfg)

    types = {n["type"] for n in cfg["nodes"].values()}
    assert "input" in types, "subgraph must have an input node"
