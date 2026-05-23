"""Phase 8.2 — hyperparameter suggestion orchestrator tests.

`suggest_hyperparams` asks Gemma 4 to propose training hyperparameters
(epochs, batch_size, augmentation_intensity, notes) given a dataset-stats
snapshot. The output is a `Hyperparameters` pydantic — out-of-range epochs,
unknown intensities, or missing fields raise `LlmValidationError`.

Tests use an in-process fake client. The opt-in integration test
(skipif IVE_OLLAMA_INTEGRATION) verifies live Gemma agreement on a
representative stats payload.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from indusia_visual_editor.services.llm.exceptions import LlmValidationError
from indusia_visual_editor.services.llm.hyperparams import (
    Hyperparameters,
    suggest_hyperparams,
)


class _FakeOllamaClient:
    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.calls: list[dict[str, Any]] = []

    async def generate(self, **kwargs) -> str:
        self.calls.append(kwargs)
        return self.response_text

    async def chat(self, **_kwargs) -> str:
        return ""


_SAMPLE_STATS: dict[str, Any] = {
    "total": 30,
    "inspected": 25,
    "skipped": 5,
    "per_criterion": {
        "missing_component": 10,
        "orientation": 5,
        "polarity_flip": 0,
        "connector_pin_bending": 0,
        "missing_pin_connector": 0,
        "lifted_pin": 0,
        "wrong_value": 8,
        "misalignment": 2,
        "solder_short": 0,
    },
    "mi_count": 18,
    "smt_count": 12,
}


@pytest.mark.asyncio
async def test_suggest_hyperparams_returns_validated_schema():
    client = _FakeOllamaClient(
        json.dumps(
            {
                "epochs": 50,
                "batch_size": 16,
                "augmentation_intensity": "medium",
                "notes": "Balanced inspected/skipped split; medium aug suffices.",
            }
        )
    )

    result = await suggest_hyperparams(
        client=client, model="gemma4:31b", dataset_stats=_SAMPLE_STATS
    )

    assert isinstance(result, Hyperparameters)
    assert result.epochs == 50
    assert result.batch_size == 16
    assert result.augmentation_intensity == "medium"
    assert result.notes  # non-empty

    # The call should have used structured-output format constraining to
    # the Hyperparameters schema; the stats payload must reach the prompt.
    assert client.calls, "client.generate was not called"
    kwargs = client.calls[0]
    assert kwargs.get("format") == Hyperparameters.model_json_schema()
    prompt = kwargs.get("prompt") or ""
    assert "missing_component" in prompt
    assert '"total": 30' in prompt or "30" in prompt


@pytest.mark.asyncio
async def test_suggest_hyperparams_rejects_out_of_range_epochs():
    # Plan §8.2 caps epochs at 5..200. 9999 must be rejected.
    client = _FakeOllamaClient(
        json.dumps(
            {
                "epochs": 9999,
                "batch_size": 16,
                "augmentation_intensity": "medium",
                "notes": "ok",
            }
        )
    )
    with pytest.raises(LlmValidationError):
        await suggest_hyperparams(
            client=client, model="gemma4:31b", dataset_stats=_SAMPLE_STATS
        )


@pytest.mark.asyncio
async def test_suggest_hyperparams_rejects_invalid_intensity():
    client = _FakeOllamaClient(
        json.dumps(
            {
                "epochs": 30,
                "batch_size": 16,
                "augmentation_intensity": "extreme",
                "notes": "ok",
            }
        )
    )
    with pytest.raises(LlmValidationError):
        await suggest_hyperparams(
            client=client, model="gemma4:31b", dataset_stats=_SAMPLE_STATS
        )


@pytest.mark.asyncio
async def test_suggest_hyperparams_rejects_non_json_response():
    client = _FakeOllamaClient("not json at all { broken }")
    with pytest.raises(LlmValidationError):
        await suggest_hyperparams(
            client=client, model="gemma4:31b", dataset_stats=_SAMPLE_STATS
        )
