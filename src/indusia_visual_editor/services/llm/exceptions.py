"""Typed errors for the LLM layer.

Callers should never see raw httpx errors — we wrap connection / timeout /
HTTP / JSON failures into `LlmError` subclasses so the route layer can map
each cleanly to an HTTP status without leaking transport details.
"""


class LlmError(Exception):
    """Base for everything the LLM client may raise."""


class LlmConnectionError(LlmError):
    """Could not reach Ollama (DNS, TCP, TLS, refused, dropped)."""


class LlmTimeoutError(LlmError):
    """Ollama did not respond within IVE_OLLAMA_TIMEOUT."""


class LlmResponseError(LlmError):
    """Ollama returned a non-2xx response or a malformed body."""


class LlmValidationError(LlmError):
    """Ollama returned JSON that did not match the expected pydantic schema."""
