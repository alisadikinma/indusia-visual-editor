"""Phase 13.3 — bearer-token gate on mutation endpoints.

GETs stay open in v1 (viewer role uses them without auth — locked in here).
Every POST/PUT/DELETE in the routes module must reject requests with a
missing, malformed, or expired Authorization header. The list below is the
canonical inventory; if a new mutation endpoint is added it MUST land in
both this list and the auth dependency wiring.
"""

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from indusia_visual_editor.config import get_config
from indusia_visual_editor.main import app
from indusia_visual_editor.services.auth.jwt_service import (
    create_access_token,
)


pytestmark = pytest.mark.skipif(
    not os.environ.get("IVE_DATABASE_URL"),
    reason="IVE_DATABASE_URL not set; start docker-compose.dev.yml postgres first.",
)


# (method, url, json) — minimal probe per protected endpoint. We expect 401
# BEFORE the body/path is validated, so URLs may reference non-existent IDs.
PROTECTED_PROBES: list[tuple[str, str, dict | None]] = [
    ("POST", "/api/projects", {"name": "x", "slug": "x"}),
    ("PUT", f"/api/projects/{uuid.uuid4()}", {"name": "x", "slug": "x"}),
    ("DELETE", f"/api/projects/{uuid.uuid4()}", None),
    ("POST", f"/api/projects/{uuid.uuid4()}/assets?kind=bom", None),
    ("POST", f"/api/projects/{uuid.uuid4()}/llm/plan", None),
    ("POST", f"/api/projects/{uuid.uuid4()}/llm/prelabel?side=top", None),
    ("POST", f"/api/projects/{uuid.uuid4()}/adapt", None),
    ("POST", f"/api/projects/{uuid.uuid4()}/labels?side=top", {"ls_json": {}}),
    ("POST", f"/api/projects/{uuid.uuid4()}/training/start", None),
    ("POST", f"/api/projects/{uuid.uuid4()}/training/suggest-hyperparams?side=top", None),
    ("POST", f"/api/projects/{uuid.uuid4()}/deploy", None),
    ("POST", "/api/edges", {"name": "x", "webhook_url": "http://x"}),
    ("PUT", f"/api/edges/{uuid.uuid4()}", {"version_policy": {"mode": "auto_pull_latest"}}),
    ("PUT", f"/api/edges/{uuid.uuid4()}/pin", {"model_name": "x", "version": "1"}),
    ("POST", f"/api/projects/{uuid.uuid4()}/chat", None),
    ("POST", f"/api/chat/{uuid.uuid4()}/stream", {"user_message": "hi"}),
    ("POST", f"/api/projects/{uuid.uuid4()}/inspection-feedback", None),
    ("PUT", f"/api/inspection-feedback/{uuid.uuid4()}", {"status": "dismissed"}),
    ("POST", f"/api/inspection-feedback/{uuid.uuid4()}/promote", None),
]


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _assert_envelope_401(body: dict) -> None:
    assert set(body.keys()) == {"status", "message", "data"}, body
    assert body["status"] is False


@pytest.mark.parametrize("method,url,payload", PROTECTED_PROBES)
@pytest.mark.asyncio
async def test_mutation_endpoints_require_bearer(
    client: AsyncClient, method: str, url: str, payload: dict | None
):
    response = await client.request(method, url, json=payload)
    assert response.status_code == 401, (method, url, response.status_code, response.text)
    _assert_envelope_401(response.json())


@pytest.mark.asyncio
async def test_mutation_endpoints_accept_valid_bearer(client: AsyncClient):
    """One representative endpoint with a valid token must NOT 401 — it may
    fail with a domain error (404, 422), but the 401 gate must let it pass."""
    email = f"middleware-{uuid.uuid4().hex[:8]}@indusiatest.dev"
    signup = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "middleware-pass-2026"},
    )
    assert signup.status_code == 201, signup.text
    token = signup.json()["data"]["access_token"]

    response = await client.delete(
        f"/api/projects/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    # Valid token + non-existent project = 404 from the domain handler.
    assert response.status_code != 401, response.text


@pytest.mark.asyncio
async def test_expired_bearer_returns_401(client: AsyncClient):
    config = get_config()
    expired = create_access_token(
        user_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        role="engineer",
        secret=config.auth_jwt_secret,
        algorithm=config.auth_jwt_algorithm,
        ttl_seconds=-1,
    )
    response = await client.delete(
        f"/api/projects/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert response.status_code == 401
    _assert_envelope_401(response.json())


@pytest.mark.asyncio
async def test_malformed_authorization_header_returns_401(client: AsyncClient):
    response = await client.delete(
        f"/api/projects/{uuid.uuid4()}",
        headers={"Authorization": "NotBearer abcdef"},
    )
    assert response.status_code == 401
    _assert_envelope_401(response.json())

    response = await client.delete(
        f"/api/projects/{uuid.uuid4()}",
        headers={"Authorization": "Bearer "},
    )
    assert response.status_code == 401
    _assert_envelope_401(response.json())


@pytest.mark.asyncio
async def test_get_endpoints_stay_open_in_v1(client: AsyncClient):
    """v1 decision point (Phase 13.3): GET endpoints do not require auth.
    Viewer role uses these without a token. This will likely tighten in
    v1.5 once the SaaS multi-tenant flow ships."""
    response = await client.get("/api/projects")
    assert response.status_code == 200, response.text
