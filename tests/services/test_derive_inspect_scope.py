"""Phase 2.2c: derive `inspect_scope` + `detector_presets` from LSF annotation.

LSF emits a flat list `result[]` where every entry references a region `id`.
A single labeled component yields three entries sharing one id:

  - rectanglelabels   → which BOM designator the region maps to
  - choices (scope)   → 'inspected' | 'skipped'
  - choices (criteria)→ list of defect criterion keys

`derive_inspect_scope` groups by id, looks up detector presets via
`data/defect_detector_mapping.yaml`, and emits one `BomItemUpdate` per
region. Unknown criteria raise `UnknownDefectCriterion` (not silently
dropped — operator must see the typo).
"""

import pytest

from indusia_visual_editor.services.inspect_scope.derive import (
    BomItemUpdate,
    LSAnnotation,
    UnknownDefectCriterion,
    derive_inspect_scope,
)


def _region(
    region_id: str,
    designator: str,
    scope: str = "inspected",
    criteria: list[str] | None = None,
    scope_mode: str = "per_component",
) -> list[dict]:
    """Build the 3-or-4 LS-JSON result entries for one labeled region."""
    out: list[dict] = [
        {
            "id": region_id,
            "type": "rectanglelabels",
            "from_name": "component",
            "to_name": "image",
            "value": {"rectanglelabels": [designator], "x": 10, "y": 10, "width": 5, "height": 5},
        },
        {
            "id": region_id,
            "type": "choices",
            "from_name": "inspect_scope",
            "to_name": "image",
            "value": {"choices": [scope]},
        },
        {
            "id": region_id,
            "type": "choices",
            "from_name": "scope_mode",
            "to_name": "image",
            "value": {"choices": [scope_mode]},
        },
    ]
    if criteria:
        out.append(
            {
                "id": region_id,
                "type": "choices",
                "from_name": "defect_criteria",
                "to_name": "image",
                "value": {"choices": criteria},
            }
        )
    return out


def test_derive_inspect_scope_from_lsf_annotation():
    annotation = LSAnnotation(
        result=_region("r-c4", "C4", "inspected", ["missing_component", "polarity_flip"])
    )

    updates = derive_inspect_scope(annotation)

    assert len(updates) == 1
    u = updates[0]
    assert isinstance(u, BomItemUpdate)
    assert u.designator == "C4"
    assert u.inspect_scope == "inspected"
    # Union of [yolo] + [yolo, orientation_classifier, polarity_template]
    assert set(u.detector_presets) == {"yolo", "orientation_classifier", "polarity_template"}


def test_derive_inspect_scope_skipped_region_emits_skipped():
    annotation = LSAnnotation(result=_region("r1", "R1", "skipped", []))
    updates = derive_inspect_scope(annotation)
    assert len(updates) == 1
    assert updates[0].inspect_scope == "skipped"
    assert updates[0].detector_presets == []


def test_derive_inspect_scope_multiple_regions():
    result = _region("r1", "R1", "skipped", []) + _region(
        "r2", "U7", "inspected", ["wrong_value"]
    )
    annotation = LSAnnotation(result=result)
    updates = derive_inspect_scope(annotation)
    assert len(updates) == 2
    by_designator = {u.designator: u for u in updates}
    assert by_designator["R1"].inspect_scope == "skipped"
    assert by_designator["U7"].inspect_scope == "inspected"
    assert set(by_designator["U7"].detector_presets) == {"yolo", "ocr"}


def test_derive_inspect_scope_unknown_criterion_raises():
    annotation = LSAnnotation(
        result=_region("r1", "R1", "inspected", ["typo_criterion_lol"])
    )
    with pytest.raises(UnknownDefectCriterion) as exc:
        derive_inspect_scope(annotation)
    assert "typo_criterion_lol" in str(exc.value)


def test_derive_inspect_scope_solder_short_only_in_whole_side_mode():
    # per_component + solder_short → must reject
    bad = LSAnnotation(
        result=_region("r1", "R1", "inspected", ["solder_short"], scope_mode="per_component")
    )
    with pytest.raises(ValueError) as exc:
        derive_inspect_scope(bad)
    assert "solder_short" in str(exc.value)
    assert "whole_side" in str(exc.value)

    # whole_side + solder_short → accepted
    ok = LSAnnotation(
        result=_region("r1", "PCB_TOP", "inspected", ["solder_short"], scope_mode="whole_side")
    )
    updates = derive_inspect_scope(ok)
    assert len(updates) == 1
    assert "anomalib_whole_side" in updates[0].detector_presets


def test_derive_inspect_scope_all_nine_criteria_have_at_least_one_detector():
    """Verification checklist: every defect criterion must map to >=1 detector."""
    from indusia_visual_editor.services.inspect_scope.derive import (
        DEFECT_CRITERIA,
        load_detector_mapping,
    )

    mapping = load_detector_mapping()
    for criterion in DEFECT_CRITERIA:
        assert criterion in mapping, f"Missing mapping for criterion '{criterion}'"
        assert len(mapping[criterion]) >= 1, f"Empty detector list for '{criterion}'"


def test_derive_inspect_scope_empty_result_returns_empty_list():
    annotation = LSAnnotation(result=[])
    assert derive_inspect_scope(annotation) == []
