"""Async HTTP client for the auto-inspect-service training endpoints.

Two surfaces:

- `start_training(model_dir)` — POST `/api/training/start` with the
  graphflow model directory path, parses back the service-assigned
  `job_id`.
- `stream_progress(job_id)` — GET `/api/training/{job_id}/stream`,
  yielding decoded JSON dicts for each `data:` SSE event the service
  emits.

Lifecycle: callers own the client and must `await aclose()` when done.
For request-scoped use inside FastAPI, prefer a `Depends` factory that
yields and closes. The constructor accepts an injected `httpx.AsyncClient`
purely for testing with `httpx.MockTransport`.

We never let raw httpx errors escape — every transport failure is
wrapped into a typed `InspectServiceError` subclass so the route layer
can map each cleanly to a 502 envelope without leaking transport
details to the operator.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from indusia_visual_editor.services.inspect_service.exceptions import (
    InspectServiceConnectionError,
    InspectServiceResponseError,
    InspectServiceTimeoutError,
)
from indusia_visual_editor.utils.otel_config import get_tracer

_tracer = get_tracer(__name__)


class TrainingClient:
    """Thin async wrapper around `auto-inspect-service`'s training surface.

    The SSE stream timeout is intentionally unbounded — training runs can
    last hours. `timeout` applies to the unary `start_training` call only;
    `stream_progress` opens its own long-lived connection.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        *,
        _http: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        # `timeout=None` on the underlying client means each call passes
        # its own timeout. For the start endpoint we pass `self._timeout`
        # explicitly; for the stream we pass `None` to allow long-lived
        # connections without ReadTimeout interruptions.
        self._http = _http or httpx.AsyncClient(
            base_url=self._base_url, timeout=timeout
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "TrainingClient":
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        await self.aclose()

    async def start_training(self, *, model_dir: str) -> str:
        """POST `/api/training/start` with `{model_dir}`, return `job_id`.

        Raises:
            InspectServiceConnectionError — service unreachable.
            InspectServiceTimeoutError — service did not respond in time.
            InspectServiceResponseError — non-2xx, malformed JSON, or
                missing `job_id` in the body.
        """

        with _tracer.start_as_current_span(
            "inspect_service.start_training",
            attributes={"inspect.model_dir": model_dir},
        ):
            try:
                r = await self._http.post(
                    "/api/training/start", json={"model_dir": model_dir}
                )
            except httpx.TimeoutException as exc:
                raise InspectServiceTimeoutError(
                    f"auto-inspect-service timed out on /api/training/start: {exc}"
                ) from exc
            except (httpx.ConnectError, httpx.TransportError) as exc:
                raise InspectServiceConnectionError(
                    f"Could not reach auto-inspect-service /api/training/start: {exc}"
                ) from exc

            if not (200 <= r.status_code < 300):
                raise InspectServiceResponseError(
                    f"auto-inspect-service /api/training/start returned "
                    f"{r.status_code}: {r.text[:300]}"
                )

            try:
                payload = r.json()
            except ValueError as exc:
                raise InspectServiceResponseError(
                    f"auto-inspect-service /api/training/start returned "
                    f"non-JSON body: {r.text[:300]}"
                ) from exc

            job_id = payload.get("job_id") if isinstance(payload, dict) else None
            if not job_id or not isinstance(job_id, str):
                raise InspectServiceResponseError(
                    f"auto-inspect-service /api/training/start did not return "
                    f"a `job_id` field: {payload!r}"
                )
            return job_id

    async def get_predictions(self, job_id: str) -> list[dict[str, Any]]:
        """GET `/api/eval/{job_id}/predictions`, return the prediction list.

        Used by the M9 eval surface to render the worst-FP / worst-FN grid.
        The service contract is a JSON array of prediction dicts (each with
        designator + bbox + verdict + is_false_positive / is_false_negative
        + score). The client round-trips the array verbatim — interpretation
        lives in the frontend.

        Raises:
            InspectServiceConnectionError — service unreachable.
            InspectServiceTimeoutError — service did not respond in time.
            InspectServiceResponseError — non-2xx, malformed JSON, or
                non-list payload.
        """

        try:
            r = await self._http.get(f"/api/eval/{job_id}/predictions")
        except httpx.TimeoutException as exc:
            raise InspectServiceTimeoutError(
                f"auto-inspect-service timed out on /api/eval/{job_id}/predictions: {exc}"
            ) from exc
        except (httpx.ConnectError, httpx.TransportError) as exc:
            raise InspectServiceConnectionError(
                f"Could not reach auto-inspect-service /api/eval/{job_id}/predictions: {exc}"
            ) from exc

        if not (200 <= r.status_code < 300):
            raise InspectServiceResponseError(
                f"auto-inspect-service /api/eval/{job_id}/predictions returned "
                f"{r.status_code}: {r.text[:300]}"
            )

        try:
            payload = r.json()
        except ValueError as exc:
            raise InspectServiceResponseError(
                f"auto-inspect-service /api/eval/{job_id}/predictions returned "
                f"non-JSON body: {r.text[:300]}"
            ) from exc

        if not isinstance(payload, list):
            raise InspectServiceResponseError(
                f"auto-inspect-service /api/eval/{job_id}/predictions returned "
                f"non-list payload: {type(payload).__name__}"
            )
        return payload

    async def stream_progress(self, job_id: str) -> AsyncIterator[dict[str, Any]]:
        """Open the SSE progress stream and yield decoded JSON dicts.

        Each `data: <json>` line in the SSE body is parsed and yielded.
        Comment lines (`: heartbeat`), blank separator lines, and other
        SSE fields (`event:`, `id:`, `retry:`) are skipped — the service
        contract is that the operator-facing payload lives in `data:`.

        Lines whose `data:` payload is not valid JSON are skipped silently
        (a malformed heartbeat must not kill the relay).

        Raises:
            InspectServiceConnectionError — service unreachable.
            InspectServiceResponseError — non-2xx response.

        Cancellation: callers may `break` out of the loop early; the
        underlying response stream closes via the `async with` block.
        """

        try:
            async with self._http.stream(
                "GET", f"/api/training/{job_id}/stream", timeout=None
            ) as r:
                if not (200 <= r.status_code < 300):
                    # Read once for diagnostics (small bounded body expected
                    # for error responses).
                    await r.aread()
                    raise InspectServiceResponseError(
                        f"auto-inspect-service /api/training/{job_id}/stream "
                        f"returned {r.status_code}: {r.text[:300]}"
                    )
                async for line in r.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith(":"):
                        # SSE comment / heartbeat
                        continue
                    if not line.startswith("data:"):
                        # `event:`, `id:`, `retry:` — not operator-facing
                        continue
                    payload = line[len("data:") :].strip()
                    if not payload:
                        continue
                    try:
                        yield json.loads(payload)
                    except json.JSONDecodeError:
                        # Malformed heartbeat — skip rather than kill the relay
                        continue
        except (httpx.ConnectError, httpx.TransportError) as exc:
            # ReadTimeout shouldn't fire (we pass timeout=None) but if a
            # different TransportError surfaces, wrap it cleanly.
            raise InspectServiceConnectionError(
                f"Could not reach auto-inspect-service "
                f"/api/training/{job_id}/stream: {exc}"
            ) from exc
