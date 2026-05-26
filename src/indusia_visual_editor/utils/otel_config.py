"""OpenTelemetry setup (Phase 14.5).

`configure_otel(endpoint, service_name)` is the single entry point —
called once from `main.py` at app startup. When `endpoint` is None (dev
default), the function still installs a TracerProvider so `get_tracer()`
calls don't crash and spans run as a no-op. When the endpoint is set
(prod), the OTLP HTTP exporter ships spans to whatever collector the
operator pointed us at.

We rely on the standard OTEL env var convention (OTEL_EXPORTER_OTLP_ENDPOINT)
rather than IVE_ prefix here because operators wiring a collector are
already in OTel land and shouldn't have to learn a vendor prefix.

Manual spans are added at the four outbound boundaries (Ollama, training
service, edge notify, ais push). FastAPI inbound spans come from
`FastAPIInstrumentor.instrument_app(app)` and httpx outbound spans come
from `HTTPXClientInstrumentor().instrument()`.
"""

from __future__ import annotations

import os
from typing import Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_CONFIGURED = False


def configure_otel(
    endpoint: Optional[str] = None,
    *,
    service_name: str = "indusia-visual-editor",
) -> None:
    """Install a global TracerProvider. Idempotent — second call is a
    no-op so the import-time bootstrap in main.py and an explicit call
    from main() don't double-export.

    `endpoint` defaults to whatever `OTEL_EXPORTER_OTLP_ENDPOINT` says;
    pass None explicitly (or set the env to empty) to keep spans local
    (no exporter attached, useful for tests and dev)."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    resolved_endpoint = (
        endpoint
        if endpoint is not None
        else os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or None
    )

    provider = TracerProvider(
        resource=Resource.create({SERVICE_NAME: service_name})
    )

    if resolved_endpoint:
        exporter = OTLPSpanExporter(endpoint=resolved_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
    _CONFIGURED = True


def get_tracer(name: str):
    """Drop-in factory for module-level tracer handles. Safe to call before
    configure_otel runs — OTel returns a ProxyTracer that resolves once
    the provider is installed."""
    return trace.get_tracer(name)


def reset_for_tests() -> None:
    """Test seam — re-arm configure_otel for the next test fixture."""
    global _CONFIGURED
    _CONFIGURED = False
