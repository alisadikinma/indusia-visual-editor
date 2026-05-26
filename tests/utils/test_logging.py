"""Phase 14.4 — structlog wiring.

Two properties matter for downstream OTel / log-aggregation:
  1. In prod mode, logger.info(msg, key=value) emits a single JSON object
     containing the message + every kwarg. Multi-line tracebacks must stay
     inside one log record so collectors can index them.
  2. Context vars set by middleware (e.g. request_id) propagate to every
     nested log call until the request handler returns.
"""

from __future__ import annotations

import io
import json
import logging

import pytest
import structlog

from indusia_visual_editor.utils.logging_config import (
    bind_context,
    clear_context,
    configure_logging,
    get_logger,
)


@pytest.fixture(autouse=True)
def _reset_structlog():
    """Each test resets the structlog config to whatever logging_config sets,
    plus clears any context vars so cross-test pollution doesn't sneak in."""
    structlog.reset_defaults()
    clear_context()
    yield
    clear_context()
    structlog.reset_defaults()


def test_prod_mode_emits_json_payload():
    buf = io.StringIO()
    configure_logging(mode="prod", stream=buf, level=logging.INFO)
    logger = get_logger("ive.test")

    logger.info("training_started", project_id="p1", train_run_id="r2")

    line = buf.getvalue().strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["event"] == "training_started"
    assert payload["project_id"] == "p1"
    assert payload["train_run_id"] == "r2"
    assert payload["logger"] == "ive.test"
    assert payload["level"] == "info"


def test_dev_mode_uses_console_renderer():
    buf = io.StringIO()
    configure_logging(mode="dev", stream=buf, level=logging.INFO)
    logger = get_logger("ive.dev")

    logger.info("running", phase="setup")

    out = buf.getvalue()
    # Console renderer NEVER emits valid JSON — assert that and that the
    # event string + key are present in some form.
    assert "running" in out
    assert "phase" in out and "setup" in out
    with pytest.raises(json.JSONDecodeError):
        json.loads(out.strip().splitlines()[-1])


def test_bind_context_propagates_to_nested_calls():
    buf = io.StringIO()
    configure_logging(mode="prod", stream=buf, level=logging.INFO)
    logger = get_logger("ive.req")

    bind_context(request_id="req-abc-123")

    # A nested helper that doesn't pass request_id explicitly:
    def _inner():
        logger.info("inner_step", step=2)

    logger.info("outer_step", step=1)
    _inner()

    lines = [json.loads(line) for line in buf.getvalue().strip().splitlines()]
    assert all(p.get("request_id") == "req-abc-123" for p in lines[-2:]), (
        f"request_id missing from nested logs: {lines}"
    )


def test_clear_context_drops_request_id():
    buf = io.StringIO()
    configure_logging(mode="prod", stream=buf, level=logging.INFO)
    logger = get_logger("ive.clear")

    bind_context(request_id="req-temp")
    clear_context()
    logger.info("after_clear")

    payload = json.loads(buf.getvalue().strip().splitlines()[-1])
    assert "request_id" not in payload
