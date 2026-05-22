"""MI vs SMT heuristic classifier (Phase 2.2b).

Pure function: package + value + designator -> ClassifyResult with
`mi_likely` (bool) and `component_type` (str). Reads regex patterns
from `data/component_taxonomy.yaml` once at import time.

This is a HINT only — `inspect_scope` is still user-controlled per-
region in the labeling canvas. The classifier just gives the canvas
sensible default badges + smart-select shortcuts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

_TAXONOMY_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "component_taxonomy.yaml"
)


@dataclass(frozen=True, slots=True)
class ClassifyResult:
    mi_likely: bool
    component_type: str | None


@lru_cache(maxsize=1)
def _load_taxonomy() -> dict:
    with _TAXONOMY_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def _compiled_patterns() -> dict:
    tax = _load_taxonomy()
    return {
        "specific_tht": {
            k: re.compile(v, re.IGNORECASE) for k, v in (tax.get("specific_tht") or {}).items()
        },
        "specific_smd": {
            k: re.compile(v, re.IGNORECASE) for k, v in (tax.get("specific_smd") or {}).items()
        },
        "smd_patterns": [re.compile(p, re.IGNORECASE) for p in (tax.get("smd_patterns") or [])],
        "tht_patterns": [re.compile(p, re.IGNORECASE) for p in (tax.get("tht_patterns") or [])],
        "designator_prefix_mi": tax.get("designator_prefix_mi") or {},
    }


def _designator_prefix(designator: str) -> str:
    """Letters at the start of the designator, e.g. 'CN12' -> 'CN'."""
    m = re.match(r"^([A-Za-z]+)", designator or "")
    return m.group(1).upper() if m else ""


def classify(package: str, value: str = "", designator: str = "") -> ClassifyResult:
    """Classify one BOM row. See module docstring for rules."""
    pats = _compiled_patterns()
    pkg = (package or "").strip()

    if pkg:
        for ctype, pattern in pats["specific_tht"].items():
            if pattern.search(pkg):
                return ClassifyResult(mi_likely=True, component_type=ctype)

        for ctype, pattern in pats["specific_smd"].items():
            if pattern.search(pkg):
                return ClassifyResult(mi_likely=False, component_type=ctype)

        for pattern in pats["smd_patterns"]:
            if pattern.search(pkg):
                return ClassifyResult(mi_likely=False, component_type="smd_generic")

        for pattern in pats["tht_patterns"]:
            if pattern.search(pkg):
                return ClassifyResult(mi_likely=True, component_type="tht_generic")

    prefix = _designator_prefix(designator)
    prefix_map = pats["designator_prefix_mi"]
    if prefix in prefix_map:
        return ClassifyResult(mi_likely=True, component_type=prefix_map[prefix])

    return ClassifyResult(mi_likely=False, component_type=None)
