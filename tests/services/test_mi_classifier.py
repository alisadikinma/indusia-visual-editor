"""Phase 2.2b MI/SMT heuristic classifier tests.

The classifier sets `mi_likely` + `component_type` hints on each parsed
BomItemDraft. It is a HINT only — `inspect_scope` stays user-controlled
per-region inside the labeling canvas. Rules per plan §2.2b:

  - smd_patterns hit  → mi_likely=False, component_type smd_*
  - tht_patterns hit  → mi_likely=True,  component_type tht_* / specific
  - designator hint + unknown package → mi_likely=True
  - otherwise (e.g., U7 / STM32F4 with no package) → mi_likely=False
    (most modern ICs are SMD; safer default than confusing the user)
"""

import pytest

from indusia_visual_editor.services.asset.mi_classifier import classify


def test_classifier_marks_smd_packages_as_auto_smt():
    result = classify(package="0805", value="10k", designator="R1")
    assert result.mi_likely is False
    assert result.component_type and result.component_type.startswith("smd")


def test_classifier_marks_through_hole_as_mi_likely():
    # Generic SIP package — no specific component_type, should fall back
    # to tht_generic via the generic THT pattern list.
    result = classify(package="SIP-3", value="", designator="U1")
    assert result.mi_likely is True
    assert result.component_type == "tht_generic"


def test_classifier_handles_unknown_package_as_mi_likely_for_safety():
    # Designator J1 = connector, classic MI part. No package → trust the
    # designator prefix, default to MI-likely so it can't disappear from
    # the operator's smart-select list.
    result = classify(package="", value="", designator="J1")
    assert result.mi_likely is True


def test_classifier_smd_ic_is_not_mi_likely():
    # Modern STM32 in LQFP-100 is SMD reflow, not MI hand-insert.
    result = classify(package="LQFP-100", value="STM32F4", designator="U7")
    assert result.mi_likely is False


def test_classifier_recognizes_electrolytic_cap_as_specific_tht():
    # Radial electrolytic capacitor — quintessential MI part. Expect a
    # specific component_type so canvas can color-code it.
    result = classify(package="Radial", value="100uF/16V", designator="C4")
    assert result.mi_likely is True
    assert result.component_type == "electrolytic_cap"


def test_classifier_recognizes_dip_ic_as_specific():
    result = classify(package="DIP-14", value="74HC04", designator="U2")
    assert result.mi_likely is True
    assert result.component_type == "dip_ic"


def test_classifier_recognizes_connector_via_designator_prefix():
    # No package, but designator J/CN/X strongly implies connector.
    result = classify(package="", value="USB-C", designator="CN3")
    assert result.mi_likely is True
    assert result.component_type == "connector"


def test_classifier_unknown_package_unknown_designator_defaults_safe():
    # Generic R designator + no package — could be either. Plan §2.2b
    # says default mi_likely=False (UI shows as unclassified, user
    # overrides per-region anyway).
    result = classify(package="", value="", designator="R99")
    assert result.mi_likely is False


def test_classifier_case_insensitive_package_matching():
    # "radial" lowercase should match same as "Radial".
    a = classify(package="radial", value="", designator="C1")
    b = classify(package="RADIAL", value="", designator="C1")
    assert a.mi_likely is True and b.mi_likely is True
    assert a.component_type == b.component_type == "electrolytic_cap"


@pytest.mark.parametrize(
    "package",
    ["0201", "0402", "0603", "0805", "1206", "QFN-32", "SOIC-8", "TSSOP-14", "BGA-256"],
)
def test_classifier_marks_all_listed_smd_packages_as_smd(package: str):
    result = classify(package=package, value="", designator="X1")
    assert result.mi_likely is False, f"{package} should be SMD-like"


@pytest.mark.parametrize(
    "package",
    ["DIP-8", "DIP-16", "PDIP-20", "TO-220", "TO-92", "Radial", "Axial", "Header-10"],
)
def test_classifier_marks_all_listed_tht_packages_as_mi(package: str):
    result = classify(package=package, value="", designator="X1")
    assert result.mi_likely is True, f"{package} should be MI-like"
