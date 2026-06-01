"""Push promoted ``defect_examples`` to auto-inspect-service (T1).

The Visual Editor accumulates operator-confirmed escapes as ``defect_examples``
(an ROI crop + one of the 9 criteria). This module ships them to the service's
``POST /setup/{model}/defect-examples`` ingest endpoint, which routes each into
the correct training track so the next retrain consumes it.

The SERVICE owns the criterion→track routing at ingest. The table below is a
local MIRROR used only to categorize the push report (OCR-skipped vs trainable)
without a round-trip. It is kept in lock-step with the service via
``test_routing_covers_exactly_the_mapping_criteria`` and the pairing note in both
repos' CLAUDE.md (§7.1 drift mitigation). NOTE: the track is NOT naively derived
from ``defect_detector_mapping.yaml`` presets — e.g. ``solder_short`` carries an
``anomalib_whole_side`` runtime preset but ingests as ``supervised``.
"""

from pathlib import Path

import yaml

_MAPPING_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "defect_detector_mapping.yaml"
)

# Mirror of auto-inspect-service `setup_defects.resolve_defect_track`.
DEFECT_TRACKS: dict[str, str] = {
    "missing_component": "supervised",
    "orientation": "supervised",
    "polarity_flip": "supervised",
    "misalignment": "supervised",
    "solder_short": "supervised",
    "missing_pin_connector": "supervised",  # in-plane absence → 2D supervised
    "connector_pin_bending": "anomaly",  # out-of-plane → anomaly
    "lifted_pin": "anomaly",  # height/3D → anomaly
    "wrong_value": "ocr_out_of_band",  # OCR-vs-BOM, not a trained crop class
}

# Out-of-plane / height defects: a single-camera 2D crop is the honest ceiling.
HONEST_LIMIT_CRITERIA = {"connector_pin_bending", "lifted_pin"}


def resolve_track(criterion: str) -> str:
    """Return the ingest track for ``criterion`` (mirror of the service)."""
    try:
        return DEFECT_TRACKS[criterion]
    except KeyError:
        raise ValueError(f"unknown defect criterion: {criterion!r}") from None


def load_mapping_criteria() -> set[str]:
    """Return the criterion keys declared in ``defect_detector_mapping.yaml``."""
    raw = yaml.safe_load(_MAPPING_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError("defect_detector_mapping.yaml must be a top-level mapping")
    return set(raw.keys())
