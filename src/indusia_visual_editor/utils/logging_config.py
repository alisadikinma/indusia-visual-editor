"""Structured logging setup (Phase 14.4).

We wrap structlog with a single entry point — `configure_logging(mode=...)`
— so the rest of the app never imports structlog directly. The two
supported modes are:

  prod  → JSON renderer, one log per record, ISO-8601 UTC timestamps,
          level name + logger name + every bound context var inlined
  dev   → console renderer with colour + key=value formatting, identical
          context-var propagation so developer tracing matches prod

`bind_context(**kvs)` and `clear_context()` use structlog's contextvars
binder; per-request middleware in main.py stamps a UUID `request_id` on
each request so nested loggers stay correlated without explicit plumbing.
"""

from __future__ import annotations

import logging
import sys
from typing import IO, Literal

import structlog
from structlog.contextvars import (
    bind_contextvars,
    clear_contextvars,
    merge_contextvars,
)

Mode = Literal["prod", "dev"]


def configure_logging(
    mode: Mode = "prod",
    *,
    stream: IO[str] | None = None,
    level: int = logging.INFO,
) -> None:
    """Idempotent setup. Call once at startup (and once per test that needs
    deterministic output). The stdlib root logger is reconfigured so legacy
    `logging.getLogger(...)` callers feed through the same renderer."""

    target = stream if stream is not None else sys.stdout

    # Reset stdlib root so structlog's PrintLoggerFactory takes over with
    # nothing left over from earlier configure_logging() calls.
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    root.setLevel(level)

    handler = logging.StreamHandler(target)
    handler.setLevel(level)
    root.addHandler(handler)

    shared_processors = [
        merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if mode == "prod":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=False)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=target),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Drop-in replacement for `logging.getLogger(__name__)` callers.

    Binds `logger=<name>` explicitly because we use `PrintLoggerFactory`
    (not stdlib), so `structlog.stdlib.add_logger_name` would crash on the
    missing `.name` attribute. Binding here keeps the JSON shape stable."""
    if name:
        return structlog.get_logger().bind(logger=name)
    return structlog.get_logger()


def bind_context(**kvs: object) -> None:
    """Bind context vars for the current async task. Subsequent `get_logger()`
    calls (anywhere in the same task) automatically include these fields."""
    bind_contextvars(**kvs)


def clear_context() -> None:
    """Drop all context vars set via `bind_context`. Called by the request
    middleware on response so per-request keys never bleed into background
    tasks scheduled by the next request."""
    clear_contextvars()


# Default mode at import time. Production overrides via configure_logging
# in main.py based on IVE_LOG_LEVEL / IVE_LOG_MODE env. Importing logging
# helpers BEFORE configure_logging() runs still works — the default
# config emits JSON to stdout at INFO.
configure_logging()
