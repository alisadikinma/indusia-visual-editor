"""Pre-label assistant — auto-locates BOM designators on a golden image.

Wraps an Ollama structured-output call. The wire format is a
`PreLabelResponse{regions: list[PreLabeledRegion]}` envelope; we unwrap
to a plain `list[PreLabeledRegion]` for the caller.

Drawing image is optional but encouraged — it acts as a spatial prior
when the golden photo has occlusion or distortion (plan §M5 Goal).

The route layer (Phase 5.3) handles fetching the asset bytes, persisting
the result, and surfacing transport errors as 502 envelopes.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

from indusia_visual_editor.services.llm.exceptions import LlmValidationError
from indusia_visual_editor.services.llm.schemas import PreLabeledRegion

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "prelabel.md"


class _LlmClientProto(Protocol):
    """Minimal client surface so we accept the real OllamaClient + test doubles."""

    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        images: list[bytes | str] | None = ...,
        format: dict[str, Any] | str | None = ...,
        options: dict[str, Any] | None = ...,
    ) -> str: ...


class _PreLabelResponse(BaseModel):
    """Wire-level envelope so Ollama's `format=` can constrain the structure.

    Kept private — callers see the unwrapped `list[PreLabeledRegion]`.
    """

    regions: list[PreLabeledRegion]


def _load_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _render_user_prompt(
    bom_designators: list[str], side: str, has_drawing: bool
) -> str:
    """The user prompt repeats the inputs alongside the system prompt so
    Ollama's chat-like generate endpoint has the BOM context in-context."""
    designators_json = json.dumps(bom_designators, ensure_ascii=False)
    drawing_hint = (
        "A PCB drawing is attached as the second image — use it as a spatial prior."
        if has_drawing
        else "No drawing is attached for this run; rely solely on the golden image."
    )
    return (
        f"{_load_system_prompt()}\n\n"
        f"## Inputs for this run\n\n"
        f"- side: {side}\n"
        f"- bom_designators: {designators_json}\n"
        f"- {drawing_hint}\n\n"
        "Locate every designator you can on the attached golden image and "
        "return JSON only."
    )


async def prelabel_designators(
    *,
    client: _LlmClientProto,
    model: str,
    bom_designators: list[str],
    golden_image: bytes,
    drawing_image: bytes | None,
    side: str,
) -> list[PreLabeledRegion]:
    """Ask Gemma 4 to locate every designator on the golden sample.

    Returns:
        list[PreLabeledRegion] — possibly empty when the model could not
        confidently locate any designator (anti-hallucination guard).

    Raises:
        LlmValidationError: response was non-JSON or did not match the
            PreLabelResponse schema.
        LlmConnectionError / LlmTimeoutError / LlmResponseError: from
            the underlying client.
    """
    if side not in ("top", "bottom"):
        raise ValueError(f"side must be 'top' or 'bottom', got {side!r}")

    has_drawing = drawing_image is not None
    prompt = _render_user_prompt(bom_designators, side, has_drawing)
    schema = _PreLabelResponse.model_json_schema()

    images: list[bytes | str] = [golden_image]
    if drawing_image is not None:
        images.append(drawing_image)

    started = time.perf_counter()
    raw = await client.generate(
        model=model,
        prompt=prompt,
        images=images,
        format=schema,
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "prelabel.designators elapsed_ms=%d designators=%d side=%s",
        elapsed_ms,
        len(bom_designators),
        side,
    )

    try:
        envelope = _PreLabelResponse.model_validate_json(raw)
    except (ValidationError, ValueError) as exc:
        raise LlmValidationError(
            f"Pre-label returned invalid JSON or schema-violating response: {exc}"
        ) from exc

    return list(envelope.regions)
