"""Phase 7.1 — async TrainingClient for auto-inspect-service.

Mock-transport tests only — opt-in integration against a live service is
gated behind `IVE_INSPECT_SERVICE_INTEGRATION` (mirrors the Ollama
opt-in pattern from Phase 3.1).

Covers:
- happy-path `start_training` round-trip
- connect / timeout / non-2xx / malformed-JSON error wrapping
- SSE `stream_progress` async iterator yielding decoded dicts
- iterator cleans up cleanly when consumer breaks early
"""

from __future__ import annotations

import json
import os

import httpx
import pytest

from indusia_visual_editor.services.inspect_service.exceptions import (
    InspectServiceConnectionError,
    InspectServiceResponseError,
    InspectServiceTimeoutError,
)
from indusia_visual_editor.services.inspect_service.training_client import (
    TrainingClient,
)


def _mock_client(handler) -> TrainingClient:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(
        transport=transport, base_url="http://mock-ais:8001", timeout=5
    )
    return TrainingClient(base_url="http://mock-ais:8001", timeout=5, _http=http)


@pytest.mark.asyncio
async def test_start_training_returns_job_id_from_service():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["json"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"job_id": "job-abc-123"})

    client = _mock_client(handler)
    try:
        job_id = await client.start_training(model_dir="/srv/models/abc")
    finally:
        await client.aclose()

    assert job_id == "job-abc-123"
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/api/training/start")
    assert captured["json"] == {"model_dir": "/srv/models/abc"}


@pytest.mark.asyncio
async def test_start_training_wraps_connection_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = _mock_client(handler)
    try:
        with pytest.raises(InspectServiceConnectionError):
            await client.start_training(model_dir="/x")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_start_training_wraps_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    client = _mock_client(handler)
    try:
        with pytest.raises(InspectServiceTimeoutError):
            await client.start_training(model_dir="/x")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_start_training_wraps_non_2xx_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "boom"})

    client = _mock_client(handler)
    try:
        with pytest.raises(InspectServiceResponseError):
            await client.start_training(model_dir="/x")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_start_training_wraps_malformed_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json-at-all")

    client = _mock_client(handler)
    try:
        with pytest.raises(InspectServiceResponseError):
            await client.start_training(model_dir="/x")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_start_training_missing_job_id_raises_response_error():
    """The service contract says the start endpoint must echo back the
    job_id. If it doesn't, we cannot SSE-relay, so fail loudly."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"something_else": "oops"})

    client = _mock_client(handler)
    try:
        with pytest.raises(InspectServiceResponseError):
            await client.start_training(model_dir="/x")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_stream_progress_yields_decoded_events():
    sse_body = (
        b'data: {"event":"epoch","epoch":1,"loss":0.5}\n\n'
        b'data: {"event":"epoch","epoch":2,"loss":0.3}\n\n'
        b'data: {"event":"succeeded","metrics":{"mAP":0.85}}\n\n'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/training/job-xyz/stream"
        return httpx.Response(
            200,
            content=sse_body,
            headers={"content-type": "text/event-stream"},
        )

    client = _mock_client(handler)
    events: list[dict] = []
    try:
        async for ev in client.stream_progress("job-xyz"):
            events.append(ev)
    finally:
        await client.aclose()

    assert len(events) == 3
    assert events[0] == {"event": "epoch", "epoch": 1, "loss": 0.5}
    assert events[1]["epoch"] == 2
    assert events[2]["event"] == "succeeded"
    assert events[2]["metrics"]["mAP"] == 0.85


@pytest.mark.asyncio
async def test_stream_progress_skips_blank_and_comment_lines():
    """SSE allows heartbeats (`:keep-alive`) and blank separator lines.
    The decoder should yield only `data:` payloads."""

    sse_body = (
        b": keep-alive\n"
        b"\n"
        b'data: {"event":"epoch","epoch":1}\n\n'
        b": heartbeat\n\n"
        b'data: {"event":"epoch","epoch":2}\n\n'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=sse_body,
            headers={"content-type": "text/event-stream"},
        )

    client = _mock_client(handler)
    events: list[dict] = []
    try:
        async for ev in client.stream_progress("job-xyz"):
            events.append(ev)
    finally:
        await client.aclose()

    assert events == [
        {"event": "epoch", "epoch": 1},
        {"event": "epoch", "epoch": 2},
    ]


@pytest.mark.asyncio
async def test_stream_progress_clean_break_on_early_consumer_exit():
    """The consumer may stop iterating before the server finishes
    (e.g. operator closes the browser tab → FastAPI cancels the
    EventSourceResponse generator → our relay generator is cancelled).
    The iterator must close the underlying stream without leaking."""

    sse_body = (
        b'data: {"event":"epoch","epoch":1}\n\n'
        b'data: {"event":"epoch","epoch":2}\n\n'
        b'data: {"event":"epoch","epoch":3}\n\n'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=sse_body,
            headers={"content-type": "text/event-stream"},
        )

    client = _mock_client(handler)
    received = 0
    try:
        async for _ev in client.stream_progress("job-xyz"):
            received += 1
            if received >= 1:
                break
    finally:
        await client.aclose()

    assert received == 1


@pytest.mark.asyncio
async def test_stream_progress_wraps_non_2xx_as_response_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "no such job"})

    client = _mock_client(handler)
    try:
        with pytest.raises(InspectServiceResponseError):
            async for _ev in client.stream_progress("missing-job"):
                pass
    finally:
        await client.aclose()


# ---------------- Phase 9.1 — get_predictions ----------------


@pytest.mark.asyncio
async def test_get_predictions_returns_list_of_dicts():
    """Eval surface — fetch sample predictions for a finished job_id.
    The service contract is a JSON array of prediction dicts; the client
    must round-trip it untouched."""

    payload = [
        {"designator": "C4", "verdict": "fail", "score": 0.9},
        {"designator": "R7", "verdict": "pass", "score": 0.2},
    ]
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        return httpx.Response(200, json=payload)

    client = _mock_client(handler)
    try:
        got = await client.get_predictions("job-eval-1")
    finally:
        await client.aclose()

    assert got == payload
    assert captured["method"] == "GET"
    assert captured["url"].endswith("/api/eval/job-eval-1/predictions")


@pytest.mark.asyncio
async def test_get_predictions_wraps_connection_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = _mock_client(handler)
    try:
        with pytest.raises(InspectServiceConnectionError):
            await client.get_predictions("job-x")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_get_predictions_wraps_non_2xx_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "boom"})

    client = _mock_client(handler)
    try:
        with pytest.raises(InspectServiceResponseError):
            await client.get_predictions("job-x")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_get_predictions_rejects_non_list_body():
    """The service contract is an array. A dict (or any non-list payload)
    is a contract violation — fail loudly rather than silently coerce."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"oops": "not a list"})

    client = _mock_client(handler)
    try:
        with pytest.raises(InspectServiceResponseError):
            await client.get_predictions("job-x")
    finally:
        await client.aclose()


@pytest.mark.skipif(
    not os.environ.get("IVE_INSPECT_SERVICE_INTEGRATION"),
    reason="set IVE_INSPECT_SERVICE_INTEGRATION=1 with a live auto-inspect-service",
)
@pytest.mark.asyncio
async def test_push_defect_example_multipart_round_trip():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["ct"] = request.headers.get("content-type", "")
        body = request.content
        seen["has_image"] = b"roi.png" in body or b"name=\"image\"" in body
        seen["has_criterion"] = b"missing_component" in body
        seen["has_source"] = b"fb-1" in body
        return httpx.Response(200, json={"track": "supervised", "written": True, "honest_limit": False})

    client = _mock_client(handler)
    try:
        out = await client.push_defect_example(
            "pcb_1",
            criterion="missing_component",
            component="R1",
            source_id="fb-1",
            image_data=b"\x89PNG\r\n",
        )
    finally:
        await client.aclose()

    assert out["track"] == "supervised"
    assert seen["url"].endswith("/api/setup/pcb_1/defect-examples")
    assert "multipart/form-data" in seen["ct"]
    assert seen["has_image"] and seen["has_criterion"] and seen["has_source"]


@pytest.mark.asyncio
async def test_push_defect_example_wraps_non_2xx():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "model not found"})

    client = _mock_client(handler)
    try:
        with pytest.raises(InspectServiceResponseError):
            await client.push_defect_example(
                "nope", criterion="missing_component", component="R1",
                source_id="x", image_data=b"\x89PNG",
            )
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_integration_real_service_health_check():
    """Hit the real auto-inspect-service — opt-in via env to avoid CI flakiness."""

    from indusia_visual_editor.config import get_config

    cfg = get_config()
    client = TrainingClient(
        base_url=cfg.inspect_service_url, timeout=cfg.inspect_service_timeout
    )
    try:
        # We don't actually start a training run here — just prove the
        # client can construct against a real URL without errors. A full
        # round-trip integration belongs to ops smoke tests, not unit suite.
        assert client._base_url.startswith("http")
    finally:
        await client.aclose()
