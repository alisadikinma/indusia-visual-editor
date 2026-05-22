"""Phase 3.3 — planner skeleton tests.

The planner is the first real LLM use case. We test it two ways:

1. Pure-mock test (always runs) — inject a fake OllamaClient that returns
   a hard-coded JSON string. Proves the planner correctly renders the
   prompt, attaches the golden image as base64, asks Ollama for
   structured output, and parses the response into ProposedPipeline.

2. Integration test (skipif IVE_OLLAMA_INTEGRATION unset) — uses a real
   Ollama. The plan §3.3 requires confirming Ollama returns
   schema-valid JSON across multiple retries for prompt tuning.
"""

from __future__ import annotations

import json
import os

import pytest

from indusia_visual_editor.services.llm.planner import (
    BomItemForPlanner,
    propose_pipeline,
)
from indusia_visual_editor.services.llm.schemas import ProposedPipeline


_TINY_PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6300010000000500010d0a2db40000000049454e44ae426082"
)


class _FakeOllamaClient:
    """In-process double of OllamaClient. Captures kwargs for assertions
    and returns a pre-baked JSON string from `generate`."""

    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.calls: list[dict] = []

    async def generate(self, **kwargs) -> str:
        self.calls.append(kwargs)
        return self.response_text

    async def chat(self, **kwargs) -> str:  # not used here
        return ""


@pytest.mark.asyncio
async def test_propose_pipeline_returns_validated_proposed_pipeline():
    fake_response = json.dumps(
        {
            "pcb_model": "NV80",
            "fiducial_strategy": "circle",
            "steps": [
                {
                    "designator": "R1",
                    "component_type": "smd_chip_passive",
                    "detectors": ["yolo"],
                    "reasoning": "Standard 0805 chip resistor.",
                }
            ],
        }
    )
    client = _FakeOllamaClient(fake_response)
    bom = [
        BomItemForPlanner(
            designator="R1", value="10kΩ", package="0805",
            component_type="smd_chip_passive", mi_likely=False, qty=1,
        )
    ]

    plan = await propose_pipeline(
        client=client, model="gemma4:31b", bom_items=bom, golden_image=_TINY_PNG_BYTES,
    )

    assert isinstance(plan, ProposedPipeline)
    assert plan.pcb_model == "NV80"
    assert len(plan.steps) == 1
    assert plan.steps[0].designator == "R1"

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["model"] == "gemma4:31b"
    assert call["images"] == [_TINY_PNG_BYTES]
    assert call["format"] is not None
    assert "R1" in call["prompt"]
    assert "10kΩ" in call["prompt"]


@pytest.mark.asyncio
async def test_propose_pipeline_raises_llm_validation_error_on_bad_json():
    from indusia_visual_editor.services.llm.exceptions import LlmValidationError

    client = _FakeOllamaClient("this is not json")
    with pytest.raises(LlmValidationError):
        await propose_pipeline(
            client=client, model="x",
            bom_items=[
                BomItemForPlanner(
                    designator="R1", value=None, package=None,
                    component_type=None, mi_likely=None, qty=None,
                )
            ],
            golden_image=_TINY_PNG_BYTES,
        )


@pytest.mark.asyncio
async def test_propose_pipeline_raises_when_schema_violated():
    from indusia_visual_editor.services.llm.exceptions import LlmValidationError

    bad = json.dumps(
        {
            "pcb_model": "X",
            "fiducial_strategy": "magic",  # not a valid literal
            "steps": [],
        }
    )
    client = _FakeOllamaClient(bad)
    with pytest.raises(LlmValidationError):
        await propose_pipeline(
            client=client, model="x",
            bom_items=[
                BomItemForPlanner(
                    designator="R1", value=None, package=None,
                    component_type=None, mi_likely=None, qty=None,
                )
            ],
            golden_image=_TINY_PNG_BYTES,
        )


@pytest.mark.asyncio
async def test_propose_pipeline_passes_format_json_schema():
    """Ollama needs format= as a JSON-schema dict so it returns valid JSON."""
    fake = json.dumps(
        {"pcb_model": "X", "fiducial_strategy": "circle", "steps": []}
    )
    client = _FakeOllamaClient(fake)
    await propose_pipeline(
        client=client, model="x",
        bom_items=[
            BomItemForPlanner(
                designator="R1", value=None, package=None,
                component_type=None, mi_likely=None, qty=None,
            )
        ],
        golden_image=_TINY_PNG_BYTES,
    )
    fmt = client.calls[0]["format"]
    assert isinstance(fmt, dict)
    assert fmt["type"] == "object"
    assert "steps" in fmt["properties"]


@pytest.mark.asyncio
async def test_propose_pipeline_includes_bom_context_in_prompt():
    fake = json.dumps({"pcb_model": "X", "fiducial_strategy": "circle", "steps": []})
    client = _FakeOllamaClient(fake)
    bom = [
        BomItemForPlanner(
            designator="C4", value="100uF", package="Radial",
            component_type="electrolytic_cap", mi_likely=True, qty=1,
        ),
        BomItemForPlanner(
            designator="U7", value="STM32F4", package="LQFP-100",
            component_type="smd_qfp", mi_likely=False, qty=1,
        ),
    ]
    await propose_pipeline(
        client=client, model="x", bom_items=bom, golden_image=_TINY_PNG_BYTES,
    )
    prompt = client.calls[0]["prompt"]
    assert "C4" in prompt
    assert "U7" in prompt
    assert "electrolytic_cap" in prompt
    assert "Radial" in prompt


@pytest.mark.skipif(
    not os.environ.get("IVE_OLLAMA_INTEGRATION"),
    reason="set IVE_OLLAMA_INTEGRATION=1 with a live Ollama on $IVE_OLLAMA_URL",
)
@pytest.mark.asyncio
async def test_integration_planner_against_real_ollama():
    from indusia_visual_editor.config import get_config
    from indusia_visual_editor.services.llm.client import OllamaClient

    cfg = get_config()
    client = OllamaClient(base_url=cfg.ollama_url, timeout=cfg.ollama_timeout)
    try:
        ok = await client.health()
        if not ok:
            pytest.skip(f"Ollama at {cfg.ollama_url} not reachable")
        bom = [
            BomItemForPlanner(
                designator="R1", value="10kΩ", package="0805",
                component_type="smd_chip_passive", mi_likely=False, qty=1,
            )
        ]
        plan = await propose_pipeline(
            client=client,
            model=cfg.ollama_model_planner,
            bom_items=bom,
            golden_image=_TINY_PNG_BYTES,
        )
        assert isinstance(plan, ProposedPipeline)
        # Schema valid; steps may be empty if model is conservative.
    finally:
        await client.aclose()
