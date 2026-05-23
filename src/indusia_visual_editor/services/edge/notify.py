"""Edge notification webhook fan-out (Phase 11.2).

Loads every registered edge from the `edges` table, POSTs the deployment
target to its `webhook_url`, retries on transport / 5xx errors with
exponential backoff (1s / 2s / 4s — three attempts total per edge), and
returns a per-edge outcome list the route layer persists to
`Deployment.edges_notified`.

A pinned edge (`version_policy.mode == 'pinned'`) is notified with its
pinned target instead of the deployment's version — the whole purpose of
pin is to NOT auto-track the latest push.

Test seam: `notify_edges(..., http_transport=...)` accepts an injected
httpx transport so the test suite uses `httpx.MockTransport`; production
calls leave transport as None and let httpx open real sockets.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from indusia_visual_editor.db.models import Deployment, Edge


logger = logging.getLogger(__name__)


# Indirected sleep so tests can patch to zero without breaking module imports.
async def _sleep(secs: float) -> None:
    await asyncio.sleep(secs)


# Retry schedule per CLAUDE.md cross-cutting ADR (3 attempts, 1/2/4s).
_BACKOFF_SECS: tuple[float, ...] = (1.0, 2.0, 4.0)


@dataclass
class NotifyOutcome:
    edge_id: str
    name: str
    ok: bool
    attempts: int
    error: str | None


def _resolve_target(
    edge: Edge,
    *,
    deployment_model_name: str,
    deployment_version: str,
) -> tuple[str, str]:
    """Pinned edges get their pinned (model_name, version); everything
    else tracks the deployment."""
    pol = edge.version_policy or {}
    if pol.get("mode") == "pinned":
        return (
            str(pol.get("model_name") or deployment_model_name),
            str(pol.get("version") or deployment_version),
        )
    return (deployment_model_name, deployment_version)


async def _notify_one(
    client: httpx.AsyncClient,
    edge: Edge,
    body: dict,
) -> NotifyOutcome:
    last_error: str | None = None
    attempts = 0
    for delay in _BACKOFF_SECS:
        attempts += 1
        try:
            r = await client.post(edge.webhook_url, json=body)
            if 200 <= r.status_code < 300:
                return NotifyOutcome(
                    edge_id=str(edge.id),
                    name=edge.name,
                    ok=True,
                    attempts=attempts,
                    error=None,
                )
            last_error = f"HTTP {r.status_code}: {r.text[:200]}"
        except (httpx.ConnectError, httpx.TimeoutException, httpx.TransportError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        # Don't sleep after the final attempt — we're about to return.
        if attempts < len(_BACKOFF_SECS):
            await _sleep(delay)
    return NotifyOutcome(
        edge_id=str(edge.id),
        name=edge.name,
        ok=False,
        attempts=attempts,
        error=last_error,
    )


async def notify_edges(
    *,
    session: AsyncSession,
    deployment: Deployment,
    pcb_name: str,
    http_transport: httpx.AsyncBaseTransport | None = None,
    timeout: float = 10.0,
) -> list[NotifyOutcome]:
    """Fan out the deployment notification to every registered edge.

    `pcb_name` is the project slug (M10 uses the project slug as the
    registry `pcb_name`). `deployment.model_version` is the version label
    pushed by the latest M10 promote.

    The function NEVER raises on per-edge failure — it returns one
    NotifyOutcome per edge so the caller can persist a complete audit
    record to `Deployment.edges_notified`.
    """

    rows = (await session.execute(select(Edge))).scalars().all()
    if not rows:
        return []

    outcomes: list[NotifyOutcome] = []
    async with httpx.AsyncClient(
        transport=http_transport, timeout=timeout
    ) as client:
        for edge in rows:
            model_name, version = _resolve_target(
                edge,
                deployment_model_name=pcb_name,
                deployment_version=deployment.model_version,
            )
            body = {"model_name": model_name, "version": version}
            outcome = await _notify_one(client, edge, body)
            outcomes.append(outcome)
            if not outcome.ok:
                logger.warning(
                    "edge notify failed: edge=%s attempts=%d error=%s",
                    outcome.name,
                    outcome.attempts,
                    outcome.error,
                )
    return outcomes
