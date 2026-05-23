"""HTTP client for the sibling `auto-inspect-service` (port 8001).

Thin async layer over `httpx`; never let raw httpx errors leak — every
transport failure is wrapped into a typed `InspectServiceError` subclass
so the route layer can map each cleanly to a `502` envelope without
exposing transport details to the operator.

Mirrors the discipline of `services.llm.client.OllamaClient`.
"""
