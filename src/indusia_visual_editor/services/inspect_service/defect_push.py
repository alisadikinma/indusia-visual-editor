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

import uuid
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from indusia_visual_editor.db.models import DefectExample

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


def _new_report(model_name: str) -> dict[str, Any]:
    return {
        "model_name": model_name,
        "total": 0,
        "pushed": 0,
        "skipped_ocr": 0,
        "needs_real_data": 0,
        "missing_crop": 0,
        "by_track": {"supervised": 0, "anomaly": 0, "ocr_out_of_band": 0},
    }


async def push_defect_examples(
    session: AsyncSession,
    project_id: uuid.UUID,
    *,
    client: Any,
    model_name: str,
    storage_root: Path,
) -> dict[str, Any]:
    """Push every promoted ``defect_example`` of a project to the service.

    Reads the project's ``defect_examples``, resolves each criterion's track,
    and POSTs the ROI crop to the service ingest endpoint (idempotent on the
    example id). OCR-out-of-band criteria are counted skipped without a POST;
    a missing ROI file on disk is counted, never fatal. Returns an aggregate
    report. ``client`` must expose ``async push_defect_example(...)`` (the
    inspect-service TrainingClient does).
    """
    rows = (
        (
            await session.execute(
                select(DefectExample).where(DefectExample.project_id == project_id)
            )
        )
        .scalars()
        .all()
    )

    report = _new_report(model_name)
    for ex in rows:
        report["total"] += 1
        track = resolve_track(ex.defect_criterion)
        report["by_track"][track] += 1

        if track == "ocr_out_of_band":
            report["skipped_ocr"] += 1
            continue

        crop_path = storage_root / ex.roi_path
        if not crop_path.exists():
            report["missing_crop"] += 1
            continue

        result = await client.push_defect_example(
            model_name,
            criterion=ex.defect_criterion,
            component=ex.designator or "",
            source_id=str(ex.id),
            image_data=crop_path.read_bytes(),
        )
        report["pushed"] += 1
        if result.get("honest_limit"):
            report["needs_real_data"] += 1

    return report
