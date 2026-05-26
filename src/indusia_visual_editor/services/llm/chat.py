"""Phase 12.2 — chat context builder for the Gemma advisor.

Stitches the system prompt + project metadata + last-N chat turns + new
user message into an `OllamaClient.chat()`-shaped message list.

Truncation strategy (in order, never violated):
1. Keep the system prompt verbatim — it defines the advisor's voice.
2. Keep at most `MAX_TURNS` (=20) most-recent prior turns.
3. Keep the new user message verbatim (it's the actual ask).
4. If aggregate char count is still over `TOKEN_BUDGET_CHARS`, drop
   prior turns from the oldest end one by one until under budget. Never
   truncate the new user message — if THAT alone overflows budget, the
   caller's input is the problem, not history.

Char count is a deliberate cheap proxy for tokens — Gemma 4's tokenizer
varies, but 4 chars/token is the common rule of thumb. 200K tokens ~=
800K chars; we leave headroom for the model's own response, so
`TOKEN_BUDGET_CHARS = 600_000`.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from indusia_visual_editor.db.models import ChatSession, Project, TrainRun
from indusia_visual_editor.utils.logging_config import get_logger


logger = get_logger(__name__)


MAX_TURNS = 20
TOKEN_BUDGET_CHARS = 600_000

_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "advisor.md"


def _load_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _format_project_block(project: Project, train_runs: list[TrainRun]) -> str:
    """Render project metadata + last-3 train_runs metrics as a single
    string block that joins the system prompt. We embed it as a fresh
    `system` message so the model knows it's stable context, not chat."""

    lines = [
        f"Project: {project.name} (status={project.status.value})",
    ]
    if not train_runs:
        lines.append("No training runs yet for this project.")
    else:
        lines.append("Latest training metrics (most-recent first):")
        for tr in train_runs:
            metrics = tr.metrics_json or {}
            map_val = metrics.get("map") or metrics.get("mAP") or "n/a"
            f1 = metrics.get("per_component_f1") or {}
            f1_brief = ", ".join(f"{k}={v}" for k, v in list(f1.items())[:5])
            lines.append(
                f"- train_run {tr.id} status={tr.status} mAP={map_val} "
                f"per_component_f1={{ {f1_brief} }}"
            )
    return "\n".join(lines)


async def build_chat_context(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    session_id: uuid.UUID,
    user_message: str,
) -> list[dict[str, Any]]:
    """Assemble the OllamaClient.chat()-shaped messages list.

    Returns:
        [
            {"role": "system", "content": <system prompt>},
            {"role": "system", "content": <project + metrics block>},
            {"role": "user"/"assistant", "content": <history...>},
            ...,
            {"role": "user", "content": <user_message>},
        ]
    """
    chat = await session.get(ChatSession, session_id)
    if chat is None:
        raise ValueError(f"chat session {session_id} not found")

    project = await session.get(Project, project_id)
    if project is None:
        raise ValueError(f"project {project_id} not found")

    # Last 3 train_runs (newest first).
    recent_trs = (
        await session.execute(
            select(TrainRun)
            .where(TrainRun.project_id == project_id)
            .order_by(TrainRun.started_at.desc())
            .limit(3)
        )
    ).scalars().all()

    system_prompt = _load_system_prompt()
    project_block = _format_project_block(project, list(recent_trs))

    # Truncate history to MAX_TURNS most-recent.
    history_all: list[dict[str, Any]] = list(chat.messages_json or [])
    history = history_all[-MAX_TURNS:]

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": project_block},
    ]
    for turn in history:
        role = turn.get("role", "user")
        content = turn.get("content", "")
        messages.append({"role": role, "content": str(content)})
    messages.append({"role": "user", "content": user_message})

    # Enforce token budget by dropping oldest history turns first.
    def _total_chars(msgs: list[dict[str, Any]]) -> int:
        return sum(len(m["content"]) for m in msgs)

    while _total_chars(messages) > TOKEN_BUDGET_CHARS:
        # The two protected anchors: index 0 (system prompt), 1 (project
        # block), and -1 (new user message). Drop the first history slot
        # (index 2) until under budget or no history left.
        if len(messages) <= 3:
            logger.warning(
                "chat context still over budget after dropping history; "
                "user_message alone is %d chars",
                len(messages[-1]["content"]),
            )
            break
        messages.pop(2)

    return messages
