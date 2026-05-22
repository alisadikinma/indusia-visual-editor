"""Phase 5.1 — pre-label assistant orchestrator tests.

`prelabel_designators` asks Gemma 4 to locate every BOM designator on a
golden image (with optional PCB drawing as spatial prior). The output is a
list of `PreLabeledRegion` validated against the schema shipped in
Phase 3.2.

Tests use a fake `_LlmClientProto` double so they run without Ollama.
The opt-in integration test (skipif IVE_OLLAMA_INTEGRATION) hits a real
Gemma to verify end-to-end behaviour.
"""

from __future__ import annotations

import json
import os
from typing import Any

import pytest

from indusia_visual_editor.services.llm.exceptions import LlmValidationError
from indusia_visual_editor.services.llm.prelabel import prelabel_designators
from indusia_visual_editor.services.llm.schemas import PreLabeledRegion


_TINY_PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6300010000000500010d0a2db40000000049454e44ae426082"
)


class _FakeOllamaClient:
    """In-process double matching the planner's `_LlmClientProto`."""

    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.calls: list[dict[str, Any]] = []

    async def generate(self, **kwargs) -> str:
        self.calls.append(kwargs)
        return self.response_text

    async def chat(self, **_kwargs) -> str:
        return ""


def _valid_response(designators: list[str], side: str = "top") -> str:
    return json.dumps(
        {
            "regions": [
                {
                    "designator": d,
                    "bbox": [0.1, 0.2, 0.05, 0.05],
                    "confidence": 0.9,
                    "side": side,
                }
                for d in designators
            ]
        }
    )


@pytest.mark.asyncio
async def test_prelabel_returns_validated_regions():
    client = _FakeOllamaClient(_valid_response(["R1", "C4", "U7"]))
    regions = await prelabel_designators(
        client=client,
        model="gemma4:31b",
        bom_designators=["R1", "C4", "U7"],
        golden_image=_TINY_PNG_BYTES,
        drawing_image=None,
        side="top",
    )

    assert len(regions) == 3
    assert all(isinstance(r, PreLabeledRegion) for r in regions)
    assert [r.designator for r in regions] == ["R1", "C4", "U7"]
    assert all(r.side == "top" for r in regions)


@pytest.mark.asyncio
async def test_prelabel_attaches_golden_only_when_no_drawing():
    client = _FakeOllamaClient(_valid_response(["R1"]))
    await prelabel_designators(
        client=client,
        model="x",
        bom_designators=["R1"],
        golden_image=_TINY_PNG_BYTES,
        drawing_image=None,
        side="top",
    )
    call = client.calls[0]
    assert call["images"] == [_TINY_PNG_BYTES]


@pytest.mark.asyncio
async def test_prelabel_attaches_both_images_when_drawing_provided():
    client = _FakeOllamaClient(_valid_response(["R1"]))
    drawing = _TINY_PNG_BYTES + b"\x00"
    await prelabel_designators(
        client=client,
        model="x",
        bom_designators=["R1"],
        golden_image=_TINY_PNG_BYTES,
        drawing_image=drawing,
        side="top",
    )
    call = client.calls[0]
    assert len(call["images"]) == 2
    assert call["images"][0] == _TINY_PNG_BYTES
    assert call["images"][1] == drawing


@pytest.mark.asyncio
async def test_prelabel_includes_bom_designators_in_prompt():
    client = _FakeOllamaClient(_valid_response(["R1"]))
    await prelabel_designators(
        client=client,
        model="x",
        bom_designators=["R1", "C4", "U7", "J1"],
        golden_image=_TINY_PNG_BYTES,
        drawing_image=None,
        side="bottom",
    )
    prompt = client.calls[0]["prompt"]
    for d in ("R1", "C4", "U7", "J1"):
        assert d in prompt
    assert "bottom" in prompt.lower()


@pytest.mark.asyncio
async def test_prelabel_passes_format_json_schema_for_structured_output():
    client = _FakeOllamaClient(_valid_response(["R1"]))
    await prelabel_designators(
        client=client,
        model="x",
        bom_designators=["R1"],
        golden_image=_TINY_PNG_BYTES,
        drawing_image=None,
        side="top",
    )
    fmt = client.calls[0]["format"]
    assert isinstance(fmt, dict)
    assert fmt["type"] == "object"
    assert "regions" in fmt["properties"]


@pytest.mark.asyncio
async def test_prelabel_raises_validation_error_on_bad_json():
    client = _FakeOllamaClient("this is not json")
    with pytest.raises(LlmValidationError):
        await prelabel_designators(
            client=client,
            model="x",
            bom_designators=["R1"],
            golden_image=_TINY_PNG_BYTES,
            drawing_image=None,
            side="top",
        )


@pytest.mark.asyncio
async def test_prelabel_raises_when_schema_violated():
    bad = json.dumps(
        {
            "regions": [
                {
                    "designator": "lowercase",  # regex violation
                    "bbox": [0.1, 0.2, 0.05, 0.05],
                    "confidence": 0.9,
                    "side": "top",
                }
            ]
        }
    )
    client = _FakeOllamaClient(bad)
    with pytest.raises(LlmValidationError):
        await prelabel_designators(
            client=client,
            model="x",
            bom_designators=["R1"],
            golden_image=_TINY_PNG_BYTES,
            drawing_image=None,
            side="top",
        )


@pytest.mark.asyncio
async def test_prelabel_empty_regions_array_is_valid():
    """Anti-hallucination guard: model returns empty array when uncertain."""
    client = _FakeOllamaClient(json.dumps({"regions": []}))
    regions = await prelabel_designators(
        client=client,
        model="x",
        bom_designators=["R1"],
        golden_image=_TINY_PNG_BYTES,
        drawing_image=None,
        side="top",
    )
    assert regions == []


@pytest.mark.skipif(
    not os.environ.get("IVE_OLLAMA_INTEGRATION"),
    reason="set IVE_OLLAMA_INTEGRATION=1 with a live Ollama on $IVE_OLLAMA_URL",
)
@pytest.mark.asyncio
async def test_integration_prelabel_against_real_ollama():
    from indusia_visual_editor.config import get_config
    from indusia_visual_editor.services.llm.client import OllamaClient

    cfg = get_config()
    client = OllamaClient(base_url=cfg.ollama_url, timeout=cfg.ollama_timeout)
    try:
        ok = await client.health()
        if not ok:
            pytest.skip(f"Ollama at {cfg.ollama_url} not reachable")
        regions = await prelabel_designators(
            client=client,
            model=cfg.ollama_model_prelabel,
            bom_designators=["R1"],
            golden_image=_TINY_PNG_BYTES,
            drawing_image=None,
            side="top",
        )
        assert isinstance(regions, list)
        for r in regions:
            assert isinstance(r, PreLabeledRegion)
    finally:
        await client.aclose()
