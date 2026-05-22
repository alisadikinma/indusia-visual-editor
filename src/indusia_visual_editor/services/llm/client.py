"""Async HTTP client for Ollama (`/api/generate`, `/api/chat`, `/api/tags`).

We never let raw httpx exceptions escape — connection, timeout, and HTTP
errors are wrapped into typed `LlmError` subclasses so the route layer
can map each cleanly to a response without leaking transport details.

Structured output: pass `format=<json-schema-dict>` to `generate()` /
`chat()` to use Ollama's JSON-schema mode. The caller is responsible for
validating the returned string against their pydantic model (Phase 3.2).

Images: `generate(images=[...])` accepts either raw bytes (we base64-
encode) or already-base64 strings (passed through unchanged). Multimodal
models such as `gemma4:31b` expect base64 PNG/JPEG.
"""

from __future__ import annotations

import base64
from typing import Any

import httpx

from indusia_visual_editor.services.llm.exceptions import (
    LlmConnectionError,
    LlmResponseError,
    LlmTimeoutError,
)


def _encode_image(img: bytes | str) -> str:
    if isinstance(img, str):
        return img  # caller already gave us base64
    return base64.b64encode(img).decode("ascii")


class OllamaClient:
    """Thin async wrapper around the Ollama REST API.

    Lifecycle: callers own the client and must `await aclose()` when done.
    For request-scoped use inside FastAPI, prefer a `Depends` factory that
    yields and closes. The constructor accepts an injected `httpx.AsyncClient`
    purely for testing with `httpx.MockTransport`.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 120.0,
        *,
        _http: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._http = _http or httpx.AsyncClient(
            base_url=self._base_url, timeout=timeout
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "OllamaClient":
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        await self.aclose()

    async def health(self) -> bool:
        """Return True iff `/api/tags` answers with 2xx. Swallows transport
        errors — health checks should never raise."""
        try:
            r = await self._http.get("/api/tags")
        except (httpx.ConnectError, httpx.TimeoutException, httpx.TransportError):
            return False
        return 200 <= r.status_code < 300

    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        images: list[bytes | str] | None = None,
        format: dict[str, Any] | str | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        body: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
        if images:
            body["images"] = [_encode_image(i) for i in images]
        if format is not None:
            body["format"] = format
        if options:
            body["options"] = options

        data = await self._post("/api/generate", body)
        return str(data.get("response", ""))

    async def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        format: dict[str, Any] | str | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if format is not None:
            body["format"] = format
        if options:
            body["options"] = options

        data = await self._post("/api/chat", body)
        message = data.get("message") or {}
        return str(message.get("content", ""))

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            r = await self._http.post(path, json=body)
        except httpx.TimeoutException as exc:
            raise LlmTimeoutError(f"Ollama timed out on {path}: {exc}") from exc
        except (httpx.ConnectError, httpx.TransportError) as exc:
            raise LlmConnectionError(f"Could not reach Ollama at {path}: {exc}") from exc

        if not (200 <= r.status_code < 300):
            raise LlmResponseError(
                f"Ollama {path} returned {r.status_code}: {r.text[:300]}"
            )

        try:
            return r.json()
        except ValueError as exc:
            raise LlmResponseError(
                f"Ollama {path} returned non-JSON body: {r.text[:300]}"
            ) from exc
