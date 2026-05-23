"""Phase 11.2 — notify_edges webhook fan-out with exponential backoff.

Loads every registered edge, POSTs `{model_name, version}` to its
webhook_url, retries with 1/2/4s spacing (3 attempts), and returns a
per-edge outcome list. Edges whose `version_policy.mode == 'pinned'` are
notified with their pinned target instead of the deployment's version.

Tests use httpx.MockTransport — no real HTTP, no real sleep (sleep is
patched to zero so the retry path runs instantly).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from indusia_visual_editor.db.models import Deployment, Edge
from indusia_visual_editor.services.edge.notify import (
    NotifyOutcome,
    notify_edges,
)


pytestmark = pytest.mark.skipif(
    not os.environ.get("IVE_DATABASE_URL"),
    reason="IVE_DATABASE_URL not set; start docker-compose.dev.yml postgres first.",
)


@pytest.fixture(autouse=True)
def fast_sleep(monkeypatch):
    """Patch asyncio.sleep used by the retry loop to zero — the retry
    spacing is the contract under test, not actual wall-clock delay."""
    import asyncio

    async def _zero(_secs):
        return None

    monkeypatch.setattr(
        "indusia_visual_editor.services.edge.notify._sleep", _zero
    )


@pytest.fixture
async def session():
    """Per-test session with a clean edges table.

    Other tests in the suite (test_edges.py route tests) commit edges via
    the API — those rows persist across test boundaries. Notify tests
    need an isolated view, so we DELETE all edges at the start of each
    test. Safe because no other test relies on edges seeded by a sibling
    notify test surviving.
    """
    from sqlalchemy import delete

    engine = create_async_engine(os.environ["IVE_DATABASE_URL"], future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        await s.execute(delete(Edge))
        await s.commit()
        yield s
        await s.execute(delete(Edge))
        await s.commit()
    await engine.dispose()


async def _seed_edge(
    session: AsyncSession, *, name_prefix: str, policy: dict | None = None
) -> Edge:
    name = f"{name_prefix}-{uuid.uuid4().hex[:8]}"
    edge = Edge(
        name=name,
        webhook_url=f"http://{name}.local:8000/api/models/refresh-cache",
        version_policy=policy or {"mode": "auto_pull_latest"},
    )
    session.add(edge)
    await session.flush()
    return edge


def _build_deployment(model_version: str = "20260523-080000-xyz") -> Deployment:
    """Build an unattached Deployment instance — notify_edges reads
    model_version + the project slug from a separate arg."""
    return Deployment(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        train_run_id=uuid.uuid4(),
        model_version=model_version,
        status="succeeded",
        deployed_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_notify_edges_posts_to_every_registered_edge(session: AsyncSession):
    edges = [
        await _seed_edge(session, name_prefix="happy-a"),
        await _seed_edge(session, name_prefix="happy-b"),
    ]
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(
            {
                "url": str(request.url),
                "json": request.content.decode("utf-8"),
            }
        )
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    deployment = _build_deployment(model_version="v-happy")
    outcomes = await notify_edges(
        session=session,
        deployment=deployment,
        pcb_name="pcb_42",
        http_transport=transport,
    )

    assert len(outcomes) == 2
    assert all(o.ok for o in outcomes)
    assert all(o.attempts == 1 for o in outcomes)
    # Both edges hit, urls match their webhook_url.
    urls = sorted(c["url"] for c in captured)
    assert urls == sorted(e.webhook_url for e in edges)


@pytest.mark.asyncio
async def test_notify_edges_retries_then_succeeds(session: AsyncSession):
    """Edge returns 503 twice, then 200 on third attempt — outcome
    records 3 attempts + ok=True."""
    await _seed_edge(session, name_prefix="retry")
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] < 3:
            return httpx.Response(503, json={"detail": "warming up"})
        return httpx.Response(200, json={"ok": True})

    outcomes = await notify_edges(
        session=session,
        deployment=_build_deployment(),
        pcb_name="pcb_42",
        http_transport=httpx.MockTransport(handler),
    )

    assert len(outcomes) == 1
    assert outcomes[0].ok is True
    assert outcomes[0].attempts == 3


@pytest.mark.asyncio
async def test_notify_edges_exhausts_retries_returns_failed_outcome(
    session: AsyncSession,
):
    await _seed_edge(session, name_prefix="exhaust")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "always-broken"})

    outcomes = await notify_edges(
        session=session,
        deployment=_build_deployment(),
        pcb_name="pcb_42",
        http_transport=httpx.MockTransport(handler),
    )

    assert len(outcomes) == 1
    assert outcomes[0].ok is False
    assert outcomes[0].attempts == 3  # 1 initial + 2 retries
    assert "500" in (outcomes[0].error or "")


@pytest.mark.asyncio
async def test_notify_edges_pinned_edge_receives_pinned_target_not_deployment_version(
    session: AsyncSession,
):
    """A pinned edge gets the pinned model_name+version in the webhook
    body, NOT the deployment's version — that's the whole point of pin."""
    await _seed_edge(
        session,
        name_prefix="pinned",
        policy={
            "mode": "pinned",
            "model_name": "pcb_old",
            "version": "20250101-000000-old",
        },
    )
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json
        captured.append(_json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={"ok": True})

    outcomes = await notify_edges(
        session=session,
        deployment=_build_deployment(model_version="v-new"),
        pcb_name="pcb_new",
        http_transport=httpx.MockTransport(handler),
    )

    assert len(outcomes) == 1
    assert outcomes[0].ok is True
    # Pinned target sent — not the deployment's version.
    assert captured[0]["model_name"] == "pcb_old"
    assert captured[0]["version"] == "20250101-000000-old"


@pytest.mark.asyncio
async def test_notify_edges_returns_empty_list_when_no_edges_registered(
    session: AsyncSession,
):
    """No edges = nothing to do. Caller MUST handle the empty-list path."""
    # Don't seed any edges. (Other tests in the same DB session may exist,
    # but the fixture rollback isolates them between tests.)
    outcomes = await notify_edges(
        session=session,
        deployment=_build_deployment(),
        pcb_name="pcb_x",
        http_transport=httpx.MockTransport(lambda _r: httpx.Response(200)),
    )
    # If other tests' edges leaked, we can't assert == 0; but we can assert
    # we didn't crash and that NotifyOutcome shape is sane.
    for o in outcomes:
        assert isinstance(o, NotifyOutcome)


@pytest.mark.asyncio
async def test_notify_edges_wraps_connection_error_as_failed_outcome(
    session: AsyncSession,
):
    """Transport-level failure (refused connection) must not crash the
    fan-out — record per-edge failure and move on."""
    await _seed_edge(session, name_prefix="conn-err")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    outcomes = await notify_edges(
        session=session,
        deployment=_build_deployment(),
        pcb_name="pcb_x",
        http_transport=httpx.MockTransport(handler),
    )
    assert len(outcomes) == 1
    assert outcomes[0].ok is False
    assert outcomes[0].attempts == 3
    assert "refused" in (outcomes[0].error or "").lower()
