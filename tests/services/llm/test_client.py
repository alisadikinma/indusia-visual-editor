"""Phase 3.1 — async OllamaClient over httpx.

Two layers of test:

1. Pure-mock tests via httpx MockTransport — always run, no Ollama needed.
   Cover: success path of generate/chat, structured-output format param,
   timeout handling, connection error wrapping, image base64 passthrough.

2. Integration test against a real Ollama server — skipif env
   `IVE_OLLAMA_INTEGRATION` not set. Pings /api/tags then runs one
   tiny `generate()` to prove end-to-end. Keeps CI cheap on machines
   without GPUs.

We never let raw httpx errors escape — every transport failure is wrapped
into a typed `LlmError` subclass.
"""

from __future__ import annotations

import base64
import json
import os

import httpx
import pytest

from indusia_visual_editor.services.llm.client import OllamaClient
from indusia_visual_editor.services.llm.exceptions import (
    LlmConnectionError,
    LlmResponseError,
    LlmTimeoutError,
)


# 1×1 transparent PNG — enough to verify base64 round-trip without
# touching the disk or shipping a binary asset.
_TINY_PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6300010000000500010d0a2db40000000049454e44ae426082"
)


def _mock_client(handler) -> OllamaClient:
    """Build an OllamaClient whose underlying httpx call uses MockTransport."""
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(
        transport=transport, base_url="http://mock-ollama:11434", timeout=5
    )
    return OllamaClient(base_url="http://mock-ollama:11434", timeout=5, _http=http)


@pytest.mark.asyncio
async def test_generate_returns_response_text():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["json"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"response": "hello, world"})

    client = _mock_client(handler)
    try:
        out = await client.generate(model="gemma4:31b", prompt="hi")
    finally:
        await client.aclose()

    assert out == "hello, world"
    assert captured["url"].endswith("/api/generate")
    assert captured["json"]["model"] == "gemma4:31b"
    assert captured["json"]["prompt"] == "hi"
    assert captured["json"]["stream"] is False


@pytest.mark.asyncio
async def test_generate_passes_format_for_structured_output():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"response": '{"k":1}'})

    schema = {"type": "object", "properties": {"k": {"type": "integer"}}}
    client = _mock_client(handler)
    try:
        await client.generate(model="x", prompt="give me k", format=schema)
    finally:
        await client.aclose()

    assert captured["json"]["format"] == schema


@pytest.mark.asyncio
async def test_generate_passes_images_as_base64():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"response": "ok"})

    client = _mock_client(handler)
    try:
        await client.generate(
            model="x",
            prompt="describe this",
            images=[_TINY_PNG_BYTES],
        )
    finally:
        await client.aclose()

    assert isinstance(captured["json"]["images"], list)
    assert len(captured["json"]["images"]) == 1
    decoded = base64.b64decode(captured["json"]["images"][0])
    assert decoded == _TINY_PNG_BYTES


@pytest.mark.asyncio
async def test_generate_already_base64_strings_pass_through():
    """If caller already base64-encoded the image, don't re-encode."""
    b64 = base64.b64encode(_TINY_PNG_BYTES).decode("ascii")
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"response": "ok"})

    client = _mock_client(handler)
    try:
        await client.generate(model="x", prompt="hi", images=[b64])
    finally:
        await client.aclose()

    assert captured["json"]["images"] == [b64]


@pytest.mark.asyncio
async def test_chat_returns_message_content():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert body["messages"] == [{"role": "user", "content": "ping"}]
        return httpx.Response(
            200, json={"message": {"role": "assistant", "content": "pong"}}
        )

    client = _mock_client(handler)
    try:
        out = await client.chat(
            model="gemma4:31b",
            messages=[{"role": "user", "content": "ping"}],
        )
    finally:
        await client.aclose()

    assert out == "pong"


@pytest.mark.asyncio
async def test_generate_wraps_connect_error_as_llm_connection_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = _mock_client(handler)
    try:
        with pytest.raises(LlmConnectionError):
            await client.generate(model="x", prompt="hi")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_generate_wraps_timeout_as_llm_timeout_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    client = _mock_client(handler)
    try:
        with pytest.raises(LlmTimeoutError):
            await client.generate(model="x", prompt="hi")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_generate_wraps_non_2xx_as_llm_response_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    client = _mock_client(handler)
    try:
        with pytest.raises(LlmResponseError):
            await client.generate(model="x", prompt="hi")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_health_returns_true_on_200():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": []})

    client = _mock_client(handler)
    try:
        assert await client.health() is True
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_health_returns_false_when_unreachable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nope", request=request)

    client = _mock_client(handler)
    try:
        assert await client.health() is False
    finally:
        await client.aclose()


@pytest.mark.skipif(
    not os.environ.get("IVE_OLLAMA_INTEGRATION"),
    reason="set IVE_OLLAMA_INTEGRATION=1 with a live Ollama on $IVE_OLLAMA_URL",
)
@pytest.mark.asyncio
async def test_integration_real_ollama_health_and_short_generate():
    """Hits a real Ollama instance — opt-in via env to avoid CI flakiness."""
    from indusia_visual_editor.config import get_config

    cfg = get_config()
    client = OllamaClient(base_url=cfg.ollama_url, timeout=cfg.ollama_timeout)
    try:
        ok = await client.health()
        if not ok:
            pytest.skip(f"Ollama at {cfg.ollama_url} did not respond to /api/tags")
        out = await client.generate(
            model=cfg.ollama_model_planner,
            prompt="Return the single word OK.",
        )
        assert isinstance(out, str) and len(out) > 0
    finally:
        await client.aclose()
