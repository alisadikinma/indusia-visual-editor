"""Derive per-region `inspect_scope` + `detector_presets` from an LSF annotation.

The labeling canvas (M6) emits a flat LS-JSON `result[]` where every entry
references a region `id`. One labeled component yields three or four
entries sharing one id:

  - rectanglelabels         (which BOM designator the box maps to)
  - choices/inspect_scope   ('inspected' | 'skipped')
  - choices/scope_mode      ('per_component' | 'whole_side')
  - choices/defect_criteria (optional list of criterion keys)

This module groups by id, validates the criteria against
`data/defect_detector_mapping.yaml`, and emits one `BomItemUpdate` per
region. Unknown criteria raise `UnknownDefectCriterion`. `solder_short`
is whole-side-only and raises `ValueError` otherwise.

The output is intentionally a list[BomItemUpdate], not a write to the
DB — the route layer (M6/M7) decides when and how to persist.
"""

from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel

_MAPPING_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "defect_detector_mapping.yaml"
)

# The nine canonical criteria — keep in sync with CLAUDE.md §8 + the
# labeling-canvas UI choice list (M6).
DEFECT_CRITERIA: tuple[str, ...] = (
    "missing_component",
    "orientation",
    "polarity_flip",
    "connector_pin_bending",
    "missing_pin_connector",
    "lifted_pin",
    "wrong_value",
    "misalignment",
    "solder_short",
)

# Criteria that are only valid when the region's scope_mode is whole_side.
_WHOLE_SIDE_ONLY: frozenset[str] = frozenset({"solder_short"})


class UnknownDefectCriterion(ValueError):
    """Raised when an annotation references a criterion not in the mapping.
    We refuse to silently drop it — operator must see the typo."""


class LSResultEntry(BaseModel):
    id: str
    type: str
    from_name: str | None = None
    to_name: str | None = None
    value: dict[str, Any]

    model_config = {"extra": "ignore"}


class LSAnnotation(BaseModel):
    """Minimal slice of an LSF annotation we care about for scope derivation."""

    result: list[LSResultEntry]

    model_config = {"extra": "ignore"}


class BomItemUpdate(BaseModel):
    """Per-region derived update. The route layer turns these into either
    bom_items column writes (designator-keyed) or a graphflow config dump."""

    designator: str
    inspect_scope: Literal["inspected", "skipped"]
    scope_mode: Literal["per_component", "whole_side"] = "per_component"
    defect_criteria: list[str] = []
    detector_presets: list[str] = []


@lru_cache(maxsize=1)
def load_detector_mapping() -> dict[str, list[str]]:
    with _MAPPING_PATH.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return {k: list(v) for k, v in raw.items()}


def _first_choice(entries: list[LSResultEntry], from_name: str) -> str | None:
    for e in entries:
        if e.type == "choices" and e.from_name == from_name:
            choices = e.value.get("choices") or []
            if choices:
                return str(choices[0])
    return None


def _criteria_list(entries: list[LSResultEntry]) -> list[str]:
    for e in entries:
        if e.type == "choices" and e.from_name == "defect_criteria":
            return [str(c) for c in (e.value.get("choices") or [])]
    return []


def _designator(entries: list[LSResultEntry]) -> str | None:
    for e in entries:
        if e.type == "rectanglelabels":
            labels = e.value.get("rectanglelabels") or []
            if labels:
                return str(labels[0])
    return None


def derive_inspect_scope(annotation: LSAnnotation) -> list[BomItemUpdate]:
    """Group LS-JSON result entries by region id and emit one update per region.

    Raises:
        UnknownDefectCriterion: a criterion not in `defect_detector_mapping.yaml`
        ValueError: solder_short used outside whole_side scope_mode
    """
    mapping = load_detector_mapping()

    by_region: dict[str, list[LSResultEntry]] = defaultdict(list)
    for entry in annotation.result:
        by_region[entry.id].append(entry)

    updates: list[BomItemUpdate] = []
    for region_id, entries in by_region.items():
        designator = _designator(entries)
        if not designator:
            # No rectanglelabels for this id — skip, it's a stray choice entry
            continue

        scope = _first_choice(entries, "inspect_scope") or "skipped"
        if scope not in ("inspected", "skipped"):
            raise ValueError(
                f"region {region_id!r}: invalid inspect_scope {scope!r}"
            )

        scope_mode = _first_choice(entries, "scope_mode") or "per_component"
        if scope_mode not in ("per_component", "whole_side"):
            raise ValueError(
                f"region {region_id!r}: invalid scope_mode {scope_mode!r}"
            )

        criteria = _criteria_list(entries) if scope == "inspected" else []

        detector_set: list[str] = []
        seen: set[str] = set()
        for criterion in criteria:
            if criterion not in mapping:
                raise UnknownDefectCriterion(
                    f"region {region_id!r}: criterion {criterion!r} is not in "
                    f"defect_detector_mapping.yaml. Known: {sorted(mapping.keys())}"
                )
            if criterion in _WHOLE_SIDE_ONLY and scope_mode != "whole_side":
                raise ValueError(
                    f"region {region_id!r}: criterion {criterion!r} is only valid "
                    f"when scope_mode='whole_side' (got {scope_mode!r})"
                )
            for det in mapping[criterion]:
                if det not in seen:
                    seen.add(det)
                    detector_set.append(det)

        updates.append(
            BomItemUpdate(
                designator=designator,
                inspect_scope=scope,  # type: ignore[arg-type]
                scope_mode=scope_mode,  # type: ignore[arg-type]
                defect_criteria=criteria,
                detector_presets=detector_set,
            )
        )

    return updates
