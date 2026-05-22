"""Planner — turns BOM + golden image into a ProposedPipeline via Ollama.

The pipeline JSON is validated against `ProposedPipeline` before returning.
Any malformed response (non-JSON, schema-violating, or missing fields) is
wrapped into `LlmValidationError` so the route layer can surface a 422.

This is the "dry-run" skeleton from plan §3.3. Phase 3.4 wires it behind
a real route and persists to the `proposed_pipelines` table.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

from indusia_visual_editor.services.llm.exceptions import LlmValidationError
from indusia_visual_editor.services.llm.schemas import ProposedPipeline

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "planner.md"


class _LlmClientProto(Protocol):
    """Minimal interface so the planner accepts either OllamaClient
    or a test double."""

    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        images: list[bytes | str] | None = ...,
        format: dict[str, Any] | str | None = ...,
        options: dict[str, Any] | None = ...,
    ) -> str: ...


class BomItemForPlanner(BaseModel):
    """Slice of BomItem the planner needs. The route layer constructs
    these from DB rows (Phase 3.4) so we don't import the SQLAlchemy
    model into the LLM service."""

    designator: str
    value: str | None = None
    package: str | None = None
    component_type: str | None = None
    mi_likely: bool | None = None
    qty: int | None = None


def _load_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _render_user_prompt(bom_items: list[BomItemForPlanner]) -> str:
    """The user message is the BOM as JSON plus a brief instruction. The
    system prompt does the heavy lifting via `_load_system_prompt`."""
    bom_json = json.dumps(
        [item.model_dump() for item in bom_items],
        ensure_ascii=False,
        indent=2,
    )
    return (
        f"{_load_system_prompt()}\n\n"
        f"## BOM\n\n```json\n{bom_json}\n```\n\n"
        "Propose the inspection pipeline for the attached golden image. "
        "Return JSON only."
    )


async def propose_pipeline(
    *,
    client: _LlmClientProto,
    model: str,
    bom_items: list[BomItemForPlanner],
    golden_image: bytes,
) -> ProposedPipeline:
    """Call Ollama with the planner prompt + golden image, parse + validate
    the response into a ProposedPipeline.

    Latency is logged so we can budget against the §9.3 ≤30s target.

    Raises:
        LlmValidationError: response was non-JSON or did not match the
            ProposedPipeline schema.
        LlmConnectionError / LlmTimeoutError / LlmResponseError: from
            the underlying client when it can't reach Ollama.
    """
    prompt = _render_user_prompt(bom_items)
    schema = ProposedPipeline.model_json_schema()

    started = time.perf_counter()
    raw = await client.generate(
        model=model,
        prompt=prompt,
        images=[golden_image],
        format=schema,
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "planner.propose_pipeline elapsed_ms=%d bom_rows=%d",
        elapsed_ms,
        len(bom_items),
    )

    try:
        return ProposedPipeline.model_validate_json(raw)
    except (ValidationError, ValueError) as exc:
        raise LlmValidationError(
            f"Planner returned invalid JSON or schema-violating response: {exc}"
        ) from exc
