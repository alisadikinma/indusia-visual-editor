"""V-1: editor-side defect-track resolver (mirror of the service routing).

The service OWNS routing at ingest; this local copy lets the push report
categorize examples (which are OCR-skipped / need real data) without a
round-trip. A drift guard keeps it in lock-step with the 9 canonical criteria.
"""

import pytest

from indusia_visual_editor.services.inspect_service.defect_push import (
    DEFECT_TRACKS,
    HONEST_LIMIT_CRITERIA,
    load_mapping_criteria,
    resolve_track,
)


@pytest.mark.parametrize(
    "criterion,track",
    [
        ("missing_component", "supervised"),
        ("orientation", "supervised"),
        ("polarity_flip", "supervised"),
        ("misalignment", "supervised"),
        ("solder_short", "supervised"),
        ("missing_pin_connector", "supervised"),
        ("connector_pin_bending", "anomaly"),
        ("lifted_pin", "anomaly"),
        ("wrong_value", "ocr_out_of_band"),
    ],
)
def test_resolve_track(criterion, track):
    assert resolve_track(criterion) == track


def test_unknown_criterion_raises():
    with pytest.raises(ValueError):
        resolve_track("not_a_criterion")


def test_honest_limit_set():
    assert HONEST_LIMIT_CRITERIA == {"connector_pin_bending", "lifted_pin"}


def test_routing_covers_exactly_the_mapping_criteria():
    # §7.1 drift guard: every criterion in defect_detector_mapping.yaml has a
    # track here, and there are no extras — a criterion added to one without the
    # other fails this test.
    assert set(DEFECT_TRACKS) == set(load_mapping_criteria())
