"""Phase 13.2 auth route tests.

Covers signup / login / refresh / logout / me. Tests use the live Postgres
container via ASGITransport. We never assert on the response cookie value
(JWT contents are tested in test_jwt.py); only that the cookie was set
HttpOnly and that the refresh endpoint round-trips through it.
"""

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from indusia_visual_editor.main import app


pytestmark = pytest.mark.skipif(
    not os.environ.get("IVE_DATABASE_URL"),
    reason="IVE_DATABASE_URL not set; start docker-compose.dev.yml postgres first.",
)


def _unique_email() -> str:
    return f"u-{uuid.uuid4().hex[:10]}@indusiatest.dev"


def _assert_envelope(body: dict, expect_status: bool) -> None:
    assert set(body.keys()) == {"status", "message", "data"}, body
    assert body["status"] is expect_status
    assert isinstance(body["message"], str)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_signup_creates_user_and_returns_access_token(client: AsyncClient):
    email = _unique_email()
    response = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "passw0rd-2026"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    _assert_envelope(body, expect_status=True)
    assert body["data"]["token_type"] == "Bearer"
    assert isinstance(body["data"]["access_token"], str)
    assert body["data"]["access_token"].count(".") == 2
    assert body["data"]["user"]["email"] == email
    assert body["data"]["user"]["role"] == "engineer"
    # Refresh cookie set HttpOnly
    assert "ive_refresh" in response.headers.get("set-cookie", "").lower()


@pytest.mark.asyncio
async def test_signup_duplicate_email_returns_409(client: AsyncClient):
    email = _unique_email()
    first = await client.post(
        "/api/auth/signup", json={"email": email, "password": "passw0rd-2026"}
    )
    assert first.status_code == 201
    second = await client.post(
        "/api/auth/signup", json={"email": email, "password": "another-pass-1"}
    )
    assert second.status_code == 409
    _assert_envelope(second.json(), expect_status=False)


@pytest.mark.asyncio
async def test_login_returns_token_for_correct_credentials(client: AsyncClient):
    email = _unique_email()
    password = "supersecret-2026"
    await client.post(
        "/api/auth/signup", json={"email": email, "password": password}
    )

    response = await client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body, expect_status=True)
    assert body["data"]["user"]["email"] == email


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client: AsyncClient):
    email = _unique_email()
    await client.post(
        "/api/auth/signup", json={"email": email, "password": "correct-pass-1"}
    )

    response = await client.post(
        "/api/auth/login", json={"email": email, "password": "wrong-pass-2"}
    )
    assert response.status_code == 401
    _assert_envelope(response.json(), expect_status=False)


@pytest.mark.asyncio
async def test_login_unknown_email_returns_401(client: AsyncClient):
    response = await client.post(
        "/api/auth/login",
        json={"email": _unique_email(), "password": "any-pass-1234"},
    )
    assert response.status_code == 401
    _assert_envelope(response.json(), expect_status=False)


@pytest.mark.asyncio
async def test_refresh_uses_httponly_cookie(client: AsyncClient):
    email = _unique_email()
    password = "refresh-secret-2026"
    await client.post(
        "/api/auth/signup", json={"email": email, "password": password}
    )
    login = await client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert login.status_code == 200

    # httpx AsyncClient persists the Set-Cookie automatically.
    refresh = await client.post("/api/auth/refresh")
    assert refresh.status_code == 200
    body = refresh.json()
    _assert_envelope(body, expect_status=True)
    assert body["data"]["user"]["email"] == email


@pytest.mark.asyncio
async def test_refresh_without_cookie_returns_401(client: AsyncClient):
    # Brand new client, no prior login.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as fresh:
        response = await fresh.post("/api/auth/refresh")
    assert response.status_code == 401
    _assert_envelope(response.json(), expect_status=False)


@pytest.mark.asyncio
async def test_me_returns_current_user_with_valid_bearer(client: AsyncClient):
    email = _unique_email()
    password = "me-secret-2026"
    signup = await client.post(
        "/api/auth/signup", json={"email": email, "password": password}
    )
    token = signup.json()["data"]["access_token"]

    response = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body, expect_status=True)
    assert body["data"]["email"] == email


@pytest.mark.asyncio
async def test_me_without_token_returns_401(client: AsyncClient):
    response = await client.get("/api/auth/me")
    assert response.status_code == 401
    _assert_envelope(response.json(), expect_status=False)
