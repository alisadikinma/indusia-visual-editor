"""Typed errors for the auto-inspect-service HTTP boundary.

Callers should never see raw httpx errors — connection / timeout / HTTP /
JSON failures are wrapped into `InspectServiceError` subclasses so the
route layer can map each cleanly to a 502 envelope.
"""


class InspectServiceError(Exception):
    """Base for anything the inspect-service client may raise."""


class InspectServiceConnectionError(InspectServiceError):
    """Could not reach auto-inspect-service (DNS, TCP, TLS, refused, dropped)."""


class InspectServiceTimeoutError(InspectServiceError):
    """auto-inspect-service did not respond within the configured timeout."""


class InspectServiceResponseError(InspectServiceError):
    """auto-inspect-service returned a non-2xx response or a malformed body."""
