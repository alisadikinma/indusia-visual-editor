"""Detector preset -> graphflow NodeSpec list mapping (Phase 4.1).

Single source of truth for the v1 graphflow vocabulary: which registered
node types each of the 13 detector presets (from
``data/defect_detector_mapping.yaml``) expands to. The subgraph builder
(Phase 4.2) imports :func:`nodes_for_detector` to splice these nodes into
``components/comp-<designator>.yaml`` between the cropper and merger.

The 49 names in :data:`KNOWN_GRAPHFLOW_NODE_TYPES` mirror the registry
documented in ``docs/specs/graphflow-config-schema.md`` section 3, which is
itself a snapshot of
``D:\\Projects\\Indusia-Inspection\\auto-inspect-service\\src\\auto_inspect_service\\schemas\\node_params.yaml``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, field_validator

# Mirror of the graphflow node-type registry enumerated in
# docs/specs/graphflow-config-schema.md section 3. The spec header label
# is "49 types" but the table itself lists 51 distinct names; we mirror
# the table. Kept hardcoded here (rather than read from
# auto-inspect-service at runtime) because this repo deliberately
# HTTP-calls auto-inspect-service in v1 and does not import its Python
# modules. When auto-inspect-service registers a new type, mirror it
# here AND in docs/specs/graphflow-config-schema.md.
KNOWN_GRAPHFLOW_NODE_TYPES: frozenset[str] = frozenset(
    {
        "anomaly_decision",
        "anomaly_dino_predictor",
        "anomaly_imgproc_predictor",
        "anomaly_predictor",
        "anomaly_result",
        "barcode_detector",
        "border_alignment_detector",
        "bright_region_crop",
        "bright_region_detector",
        "bright_region_split",
        "check_missing",
        "circle_alignment_detector",
        "data_matrix_detector",
        "fiducial_detector",
        "fiducial_detector_v2",
        "golden_reference",
        "graph",
        "input",
        "light_background_detector",
        "lifted_pin_detector",
        "merge_result",
        "merge_tile_result",
        "ocr_model",
        "orb_alignment_detector",
        "orientation_classifier",
        "rejected",
        "save_image",
        "script",
        "show_image",
        "static_box",
        "switch",
        "template_match_classifier",
        "template_match_detector",
        "threshold_crop",
        "threshold_detector",
        "threshold_fiducial_detector",
        "tile_crop",
        "transform_anomaly_result",
        "transform_barcode_result",
        "transform_box_result",
        "transform_data_matrix_result",
        "transform_light_background_result",
        "transform_ocr_result",
        "transform_probs_result",
        "transform_result",
        "transform_single_result",
        "yolo_anomaly_predictor",
        "yolo_crop",
        "yolo_estimator",
        "yolo_fiducial_detector",
        "yolo_lifted_pin_detector",
    }
)


class UnknownDetectorPreset(ValueError):
    """Raised when a caller asks for a preset not declared in the YAML.

    Never default to ``yolo`` or any other preset on typo - silent
    fallbacks mask config drift. The caller (Gemma planner) must surface
    the bad preset name so the user can correct it.
    """


class NodeSpec(BaseModel):
    """A single graphflow node declaration: type plus optional params block.

    Mirrors the shape consumed by auto-inspect-service when it parses
    ``components/comp-*.yaml`` subgraphs (one entry under ``nodes:``).
    """

    type: str
    params: dict[str, Any] | None = None

    @field_validator("type")
    @classmethod
    def _type_must_be_registered(cls, v: str) -> str:
        if v not in KNOWN_GRAPHFLOW_NODE_TYPES:
            raise ValueError(
                f"node type {v!r} is not in the 49-name graphflow registry"
            )
        return v


_YAML_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "detector_to_nodes.yaml"
)


@lru_cache(maxsize=1)
def _load_mapping() -> dict[str, list[dict[str, Any]]]:
    with _YAML_PATH.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise RuntimeError(
            f"detector_to_nodes.yaml must be a top-level mapping, got {type(raw)!r}"
        )
    return raw


def nodes_for_detector(preset: str) -> list[NodeSpec]:
    """Return the ordered NodeSpec list for one detector preset.

    Raises :class:`UnknownDetectorPreset` if ``preset`` is not a top-level
    key in ``data/detector_to_nodes.yaml``. NodeSpec validation rejects any
    node type not in :data:`KNOWN_GRAPHFLOW_NODE_TYPES`.
    """
    mapping = _load_mapping()
    if preset not in mapping:
        raise UnknownDetectorPreset(
            f"detector preset {preset!r} not declared in detector_to_nodes.yaml"
        )
    entries = mapping[preset]
    return [NodeSpec(**entry) for entry in entries]
