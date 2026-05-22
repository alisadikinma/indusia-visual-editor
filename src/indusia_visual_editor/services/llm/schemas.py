"""Pydantic structured-output schemas for Gemma JSON responses.

Mirrors CLAUDE.md §9.2 and plan §5.4. Every LLM call uses Ollama's
JSON-schema mode (`format=<this-schema.model_json_schema()>`) — we never
trust raw free-form text. If validation fails the route layer raises
`LlmValidationError`.

Four use cases:
  - ProposedPipeline   — planner (M3/M4)
  - PreLabeledRegion   — pre-label assistant (M5)
  - DefectVerdict      — runtime defect judge (v1.5 — NOT in MVP)
  - ChatTurn           — training/diagnostics advisor (M12)
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Detector preset names accepted by auto-inspect-service. Keep in sync
# with data/defect_detector_mapping.yaml (Phase 2.2c).
Detector = Literal[
    "yolo",
    "yolo_fine_grained",
    "anomalib_roi",
    "anomalib_whole_side",
    "ocr",
    "barcode",
    "template_match",
    "polarity_template",
    "orientation_classifier",
    "lifted_pin",
    "pin_count_check",
    "border_alignment",
    "threshold",
]

FiducialStrategy = Literal["circle", "orb", "yolo", "threshold"]

DesignatorPattern = r"^[A-Z]+[0-9]+$"


class ProposedPipelineStep(BaseModel):
    """One per BOM designator the planner thinks should be inspected."""

    model_config = ConfigDict(extra="forbid")

    designator: str = Field(pattern=DesignatorPattern)
    component_type: str
    detectors: list[Detector]
    reasoning: str


class ProposedPipeline(BaseModel):
    """Full plan emitted by the LLM for one PCB side. Persisted to
    `proposed_pipelines` table in Phase 3.4."""

    model_config = ConfigDict(extra="forbid")

    pcb_model: str
    fiducial_strategy: FiducialStrategy
    steps: list[ProposedPipelineStep]


class PreLabeledRegion(BaseModel):
    """One auto-suggested bounding box from the pre-label assistant.
    Coordinates are normalized to [0, 1] so they are resolution-agnostic
    when the canvas later renders them."""

    model_config = ConfigDict(extra="forbid")

    designator: str = Field(pattern=DesignatorPattern)
    bbox: tuple[float, float, float, float]
    confidence: float = Field(ge=0.0, le=1.0)
    side: Literal["top", "bottom"]

    @field_validator("bbox")
    @classmethod
    def _bbox_normalized(cls, v: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        for component in v:
            if not (0.0 <= component <= 1.0):
                raise ValueError(
                    f"bbox component {component!r} outside normalized [0, 1] range"
                )
        return v


class DefectVerdict(BaseModel):
    """Runtime judge response. v1.5 only — NOT used in MVP per plan §9.1."""

    model_config = ConfigDict(extra="forbid")

    verdict: Literal["pass", "fail", "uncertain"]
    confidence: float = Field(ge=0.0, le=1.0)
    reason_short: str
    reason_detail: str


class ChatTurn(BaseModel):
    """One turn in the M12 advisor chat. Streamed to the UI."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant", "system"]
    content: str
