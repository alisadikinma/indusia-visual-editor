"""Phase 8.2 — hyperparameter suggestion via Gemma 4.

Wraps an Ollama structured-output call. Returns a pydantic-validated
`Hyperparameters` so out-of-range epochs (>200), invalid intensities,
non-JSON responses, etc. all surface as `LlmValidationError` and the
route layer can convert them into 502 envelopes (same pattern as the
M5 pre-label and M3 planner orchestrators).

Plan §8.2: `epochs` in [5, 200]; `batch_size` in [4, 64];
`augmentation_intensity` in {'low','medium','high'}.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, ValidationError

from indusia_visual_editor.services.llm.exceptions import LlmValidationError
from indusia_visual_editor.utils.logging_config import get_logger

logger = get_logger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "hyperparams.md"


class _LlmClientProto(Protocol):
    """Minimal client surface — same shape as the planner / pre-label uses."""

    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        images: list[bytes | str] | None = ...,
        format: dict[str, Any] | str | None = ...,
        options: dict[str, Any] | None = ...,
    ) -> str: ...


class Hyperparameters(BaseModel):
    """Bounded hyperparameter suggestion the Gate-1 panel surfaces to the
    operator. Bounds enforced server-side so a malformed LLM response can
    never sneak through to `/api/training/start`."""

    epochs: int = Field(ge=5, le=200)
    batch_size: int = Field(ge=4, le=64)
    augmentation_intensity: Literal["low", "medium", "high"]
    notes: str = Field(min_length=1, max_length=500)


def _load_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _render_user_prompt(dataset_stats: dict[str, Any]) -> str:
    """The system prompt + the stats payload + a short instruction.
    Mirrors planner/prelabel patterns so behaviour stays predictable."""
    stats_json = json.dumps(dataset_stats, ensure_ascii=False, indent=2)
    return (
        f"{_load_system_prompt()}\n\n"
        f"## Dataset statistics\n\n```json\n{stats_json}\n```\n\n"
        "Propose hyperparameters for this dataset. Return JSON only."
    )


async def suggest_hyperparams(
    *,
    client: _LlmClientProto,
    model: str,
    dataset_stats: dict[str, Any],
) -> Hyperparameters:
    """Ask Gemma 4 to propose training hyperparameters from the stats payload.

    Raises:
        LlmValidationError: response was non-JSON or did not match the
            Hyperparameters schema (out-of-range, unknown intensity, ...).
        LlmConnectionError / LlmTimeoutError / LlmResponseError: from the
            underlying client when it can't reach Ollama.
    """
    prompt = _render_user_prompt(dataset_stats)
    schema = Hyperparameters.model_json_schema()

    started = time.perf_counter()
    raw = await client.generate(
        model=model,
        prompt=prompt,
        format=schema,
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "hyperparams.suggest elapsed_ms=%d total=%s inspected=%s",
        elapsed_ms,
        dataset_stats.get("total"),
        dataset_stats.get("inspected"),
    )

    try:
        return Hyperparameters.model_validate_json(raw)
    except (ValidationError, ValueError) as exc:
        raise LlmValidationError(
            f"Hyperparameters returned invalid JSON or schema-violating response: {exc}"
        ) from exc
