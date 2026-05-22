"""Phase 3.2 — pydantic structured-output schemas for LLM JSON responses.

Schemas mirror CLAUDE.md §9.2 + plan §5.4: ProposedPipelineStep,
ProposedPipeline, PreLabeledRegion, DefectVerdict, ChatTurn. We test
roundtrip from raw JSON (what Ollama returns) and invalid payloads
that must raise ValidationError.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from indusia_visual_editor.services.llm.schemas import (
    ChatTurn,
    DefectVerdict,
    PreLabeledRegion,
    ProposedPipeline,
    ProposedPipelineStep,
)


# ---------------------- ProposedPipeline ----------------------

VALID_PLAN_JSON = json.dumps(
    {
        "pcb_model": "NV80",
        "fiducial_strategy": "circle",
        "steps": [
            {
                "designator": "R1",
                "component_type": "smd_chip_passive",
                "detectors": ["yolo"],
                "reasoning": "Standard 0805 chip resistor — yolo handles it.",
            },
            {
                "designator": "U7",
                "component_type": "smd_qfp",
                "detectors": ["yolo", "ocr"],
                "reasoning": "Need part-number readback in addition to presence.",
            },
        ],
    }
)


def test_proposed_pipeline_validates_well_formed_json():
    plan = ProposedPipeline.model_validate_json(VALID_PLAN_JSON)
    assert plan.pcb_model == "NV80"
    assert plan.fiducial_strategy == "circle"
    assert len(plan.steps) == 2
    assert plan.steps[0].designator == "R1"
    assert plan.steps[1].detectors == ["yolo", "ocr"]


def test_proposed_pipeline_step_designator_must_match_pattern():
    bad = {
        "designator": "lowercase",  # must be ^[A-Z]+[0-9]+$
        "component_type": "smd",
        "detectors": ["yolo"],
        "reasoning": "x",
    }
    with pytest.raises(ValidationError):
        ProposedPipelineStep.model_validate(bad)


def test_proposed_pipeline_rejects_unknown_detector():
    bad = {
        "pcb_model": "X",
        "fiducial_strategy": "circle",
        "steps": [
            {
                "designator": "R1",
                "component_type": "x",
                "detectors": ["not_a_real_detector"],
                "reasoning": "y",
            }
        ],
    }
    with pytest.raises(ValidationError):
        ProposedPipeline.model_validate(bad)


def test_proposed_pipeline_rejects_unknown_fiducial_strategy():
    bad = {
        "pcb_model": "X",
        "fiducial_strategy": "magic",  # not in literal
        "steps": [],
    }
    with pytest.raises(ValidationError):
        ProposedPipeline.model_validate(bad)


def test_proposed_pipeline_json_schema_is_exportable():
    """Ollama's `format=` param needs a JSON schema dict — must not crash."""
    schema = ProposedPipeline.model_json_schema()
    assert schema["type"] == "object"
    assert "steps" in schema["properties"]


# ---------------------- PreLabeledRegion ----------------------

def test_pre_labeled_region_accepts_normalized_bbox():
    region = PreLabeledRegion.model_validate(
        {
            "designator": "R1",
            "bbox": [0.10, 0.20, 0.05, 0.05],
            "confidence": 0.87,
            "side": "top",
        }
    )
    assert region.designator == "R1"
    assert region.bbox == (0.10, 0.20, 0.05, 0.05)
    assert 0.0 <= region.confidence <= 1.0


def test_pre_labeled_region_rejects_bbox_out_of_range():
    with pytest.raises(ValidationError):
        PreLabeledRegion.model_validate(
            {
                "designator": "R1",
                "bbox": [0.1, 0.2, 1.5, 0.5],  # 1.5 > 1.0
                "confidence": 0.5,
                "side": "top",
            }
        )


def test_pre_labeled_region_rejects_confidence_out_of_range():
    with pytest.raises(ValidationError):
        PreLabeledRegion.model_validate(
            {
                "designator": "R1",
                "bbox": [0.1, 0.1, 0.1, 0.1],
                "confidence": 1.5,
                "side": "top",
            }
        )


def test_pre_labeled_region_rejects_unknown_side():
    with pytest.raises(ValidationError):
        PreLabeledRegion.model_validate(
            {
                "designator": "R1",
                "bbox": [0.1, 0.1, 0.1, 0.1],
                "confidence": 0.5,
                "side": "left",  # not 'top'/'bottom'
            }
        )


# ---------------------- DefectVerdict ----------------------

def test_defect_verdict_accepts_pass_fail_uncertain():
    for v in ("pass", "fail", "uncertain"):
        ok = DefectVerdict.model_validate(
            {
                "verdict": v,
                "confidence": 0.9,
                "reason_short": "ok",
                "reason_detail": "longer explanation here",
            }
        )
        assert ok.verdict == v


def test_defect_verdict_rejects_unknown_verdict():
    with pytest.raises(ValidationError):
        DefectVerdict.model_validate(
            {
                "verdict": "maybe",
                "confidence": 0.5,
                "reason_short": "x",
                "reason_detail": "y",
            }
        )


# ---------------------- ChatTurn ----------------------

def test_chat_turn_accepts_user_and_assistant():
    for role in ("user", "assistant", "system"):
        turn = ChatTurn.model_validate({"role": role, "content": "hi"})
        assert turn.role == role


def test_chat_turn_rejects_unknown_role():
    with pytest.raises(ValidationError):
        ChatTurn.model_validate({"role": "bot", "content": "hi"})
