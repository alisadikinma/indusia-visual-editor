"""Pydantic schema tests for the inspection-feedback loop (Phase B).

Non-DB — these run fully here (no IVE_DATABASE_URL needed). Validates that
the Literal sets match the table CHECK constraints and that FeedbackRead
round-trips a plain attribute object via from_attributes.
"""

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from indusia_visual_editor.schemas.inspection_feedback import (
    DefectExampleRead,
    FeedbackCurate,
    FeedbackIngest,
    FeedbackRead,
)


def test_feedback_ingest_rejects_bad_operator_mark():
    with pytest.raises(ValidationError):
        FeedbackIngest(
            model_verdict="pass",
            operator_mark="bogus-mark",
        )


def test_feedback_ingest_accepts_valid_payload_and_ignores_extra():
    ingest = FeedbackIngest(
        designator="R1",
        model_verdict="pass",
        operator_mark="escape",
        defect_criterion="missing_component",
        inspection_ts=datetime.now(timezone.utc),
        edge_id=uuid.uuid4(),
        train_run_id=uuid.uuid4(),
        unexpected_field="ignored",  # extra="ignore"
    )
    assert ingest.operator_mark == "escape"
    assert ingest.defect_criterion == "missing_component"


def test_feedback_ingest_rejects_bad_verdict():
    with pytest.raises(ValidationError):
        FeedbackIngest(model_verdict="maybe", operator_mark="confirmed")


def test_feedback_curate_fields_optional():
    curate = FeedbackCurate()
    assert curate.operator_mark is None
    assert curate.status is None

    curate2 = FeedbackCurate(operator_mark="confirmed", status="curated")
    assert curate2.operator_mark == "confirmed"
    assert curate2.status == "curated"


def test_feedback_curate_rejects_bad_status():
    with pytest.raises(ValidationError):
        FeedbackCurate(status="archived")


def test_feedback_read_from_attributes():
    class _Row:
        id = uuid.uuid4()
        project_id = uuid.uuid4()
        edge_id = None
        train_run_id = None
        designator = "U7"
        model_verdict = "pass"
        operator_mark = "escape"
        defect_criterion = "lifted_pin"
        roi_path = "pid/feedback_roi/abc.jpg"
        roi_sha256 = "a" * 64
        status = "new"
        inspection_ts = None
        created_at = datetime.now(timezone.utc)

    read = FeedbackRead.model_validate(_Row())
    assert read.designator == "U7"
    assert read.operator_mark == "escape"
    assert read.status == "new"


def test_defect_example_read_from_attributes():
    class _Row:
        id = uuid.uuid4()
        project_id = uuid.uuid4()
        source_feedback_id = uuid.uuid4()
        designator = "C3"
        defect_criterion = "polarity_flip"
        roi_path = "pid/feedback_roi/def.jpg"
        roi_sha256 = "b" * 64
        created_at = datetime.now(timezone.utc)

    read = DefectExampleRead.model_validate(_Row())
    assert read.defect_criterion == "polarity_flip"
    assert read.roi_sha256 == "b" * 64
