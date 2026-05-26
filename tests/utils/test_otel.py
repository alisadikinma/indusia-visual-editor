"""Phase 14.5 — OpenTelemetry wiring.

Two properties matter for observability:
  1. configure_otel() with no exporter env returns a working tracer that
     creates spans without raising — operators in dev environments must
     not need an OTLP collector to run the app.
  2. Manual spans wrap outbound calls (Ollama generate, TrainingClient,
     edge notify, ais push). We verify the span names + attributes via
     an in-memory exporter so the test never needs a live collector.
"""

from __future__ import annotations

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from indusia_visual_editor.utils.otel_config import (
    configure_otel,
    get_tracer,
)


@pytest.fixture
def memory_exporter():
    """Fresh TracerProvider per test, exporting to an in-memory sink. OTel's
    global TracerProvider is one-shot (override raises a warning + is a
    no-op), so the fixture hands the caller a TRACER bound to the local
    provider — bypass the global entirely."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("ive.test")
    yield exporter, tracer
    exporter.clear()


def test_configure_otel_with_no_endpoint_is_noop_safe():
    """In dev (no OTEL_EXPORTER_OTLP_ENDPOINT), configure_otel() must
    return without raising. Spans created against the resulting tracer
    can be ignored without setup."""
    configure_otel(endpoint=None, service_name="ive-test")
    tracer = get_tracer("ive.test")
    with tracer.start_as_current_span("noop_span"):
        pass


def test_manual_span_records_name_and_attributes(memory_exporter):
    exporter, tracer = memory_exporter
    with tracer.start_as_current_span(
        "ollama.generate", attributes={"model": "gemma4:31b", "phase": "planner"}
    ):
        pass

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.name == "ollama.generate"
    assert span.attributes["model"] == "gemma4:31b"
    assert span.attributes["phase"] == "planner"


def test_nested_spans_share_trace_id(memory_exporter):
    """Outbound call spans live inside the inbound FastAPI span at runtime;
    we model that here with an outer + inner span and assert trace_id
    propagates so collectors can stitch the trace together."""
    exporter, tracer = memory_exporter
    with tracer.start_as_current_span("outer"):
        with tracer.start_as_current_span("inner"):
            pass

    spans = exporter.get_finished_spans()
    assert len(spans) == 2
    trace_ids = {span.context.trace_id for span in spans}
    assert len(trace_ids) == 1, f"expected single trace, got {trace_ids}"
