"""Phase 13.2 — JWT token service.

Pure unit tests against the token service. Login endpoint integration lives
in tests/routes/test_auth.py. We never sign with the dev default secret in
tests — `auth_jwt_secret` is overridden per-test so leaks don't compromise
real installs.
"""

import time
import uuid

import pytest

from indusia_visual_editor.services.auth.jwt_service import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    verify_token,
)


SECRET = "test-secret-only-for-this-module"
ALG = "HS256"


def test_create_and_verify_access_token_roundtrip():
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    token = create_access_token(
        user_id=user_id,
        organization_id=org_id,
        role="engineer",
        secret=SECRET,
        algorithm=ALG,
        ttl_seconds=3600,
    )
    assert isinstance(token, str) and token.count(".") == 2

    payload = verify_token(token, secret=SECRET, algorithm=ALG)
    assert payload.user_id == user_id
    assert payload.organization_id == org_id
    assert payload.role == "engineer"
    assert payload.token_type == "access"


def test_verify_token_rejects_wrong_secret():
    token = create_access_token(
        user_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        role="admin",
        secret=SECRET,
        algorithm=ALG,
        ttl_seconds=3600,
    )
    with pytest.raises(InvalidTokenError):
        verify_token(token, secret="another-secret", algorithm=ALG)


def test_verify_token_rejects_expired():
    token = create_access_token(
        user_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        role="viewer",
        secret=SECRET,
        algorithm=ALG,
        ttl_seconds=-1,  # already expired
    )
    # Tiny sleep so the clock advances past "now"
    time.sleep(0.01)
    with pytest.raises(InvalidTokenError):
        verify_token(token, secret=SECRET, algorithm=ALG)


def test_verify_token_rejects_malformed():
    with pytest.raises(InvalidTokenError):
        verify_token("not.a.jwt", secret=SECRET, algorithm=ALG)
    with pytest.raises(InvalidTokenError):
        verify_token("", secret=SECRET, algorithm=ALG)


def test_refresh_token_carries_distinct_type_claim():
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    refresh = create_refresh_token(
        user_id=user_id,
        organization_id=org_id,
        secret=SECRET,
        algorithm=ALG,
        ttl_seconds=60 * 60 * 24,
    )
    payload = verify_token(refresh, secret=SECRET, algorithm=ALG)
    assert payload.token_type == "refresh"
    # Refresh tokens deliberately omit role — the engine re-fetches it on use
    assert payload.role is None
