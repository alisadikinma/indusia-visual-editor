"""Phase 0.1 health endpoint TDD anchor.

Drives the minimum viable FastAPI app: a single GET /health endpoint that
returns the canonical {status, message, data} response shape used across all
Indusia inspection services.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from indusia_visual_editor.main import app


@pytest.mark.asyncio
async def test_health_endpoint_returns_status_ok():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "status": True,
        "message": "ok",
        "data": {"version": "0.1.0"},
    }
