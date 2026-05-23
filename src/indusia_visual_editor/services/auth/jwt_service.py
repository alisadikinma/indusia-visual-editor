"""JWT bearer + refresh token primitives.

Two token types share the same signing key but encode different `type`
claims so an access token cannot be replayed as a refresh and vice
versa. Access tokens carry `role` so the RBAC layer (Phase 13.4) can
authorise without a DB roundtrip on every request; refresh tokens
deliberately omit role so a stale refresh after a role change is forced
to re-resolve role from the database when minting the next access.

All signing/verification happens through this module — callers never
import `jose` directly. This makes algorithm rotation a one-file change.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from jose import JWTError, jwt


TokenType = Literal["access", "refresh"]


class InvalidTokenError(Exception):
    """Raised on signature mismatch, expired token, or any decode failure.

    The route layer maps this to a 401 envelope; the message is opaque on
    purpose so brute-force probes cannot distinguish failure modes."""


@dataclass(frozen=True)
class TokenPayload:
    user_id: uuid.UUID
    organization_id: uuid.UUID
    role: str | None
    token_type: TokenType
    expires_at: datetime


def _build_claims(
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    role: str | None,
    token_type: TokenType,
    ttl_seconds: int,
) -> dict:
    now = datetime.now(tz=timezone.utc)
    exp = now + timedelta(seconds=ttl_seconds)
    claims: dict = {
        "sub": str(user_id),
        "org": str(organization_id),
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    if role is not None:
        claims["role"] = role
    return claims


def create_access_token(
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    role: str,
    secret: str,
    algorithm: str = "HS256",
    ttl_seconds: int = 3600,
) -> str:
    claims = _build_claims(
        user_id=user_id,
        organization_id=organization_id,
        role=role,
        token_type="access",
        ttl_seconds=ttl_seconds,
    )
    return jwt.encode(claims, secret, algorithm=algorithm)


def create_refresh_token(
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    secret: str,
    algorithm: str = "HS256",
    ttl_seconds: int = 60 * 60 * 24 * 14,
) -> str:
    claims = _build_claims(
        user_id=user_id,
        organization_id=organization_id,
        role=None,
        token_type="refresh",
        ttl_seconds=ttl_seconds,
    )
    return jwt.encode(claims, secret, algorithm=algorithm)


def verify_token(token: str, *, secret: str, algorithm: str = "HS256") -> TokenPayload:
    if not token:
        raise InvalidTokenError("empty token")
    try:
        claims = jwt.decode(token, secret, algorithms=[algorithm])
    except JWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    try:
        user_id = uuid.UUID(claims["sub"])
        organization_id = uuid.UUID(claims["org"])
        token_type = claims["type"]
        exp = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
    except (KeyError, ValueError, TypeError) as exc:
        raise InvalidTokenError(f"malformed claims: {exc}") from exc

    if token_type not in ("access", "refresh"):
        raise InvalidTokenError(f"unknown token type {token_type!r}")

    return TokenPayload(
        user_id=user_id,
        organization_id=organization_id,
        role=claims.get("role"),
        token_type=token_type,  # type: ignore[arg-type]
        expires_at=exp,
    )
