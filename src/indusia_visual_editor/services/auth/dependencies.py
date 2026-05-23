"""FastAPI dependencies for auth-protected routes (Phase 13.3).

Reading `Authorization: Bearer <token>` and resolving to a real `User` row
on every protected handler. The 401 response uses the canonical envelope
so the Vue layer can always parse it the same shape.
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from indusia_visual_editor.config import AppConfig, get_config
from indusia_visual_editor.db.models import User
from indusia_visual_editor.db.session import get_session
from indusia_visual_editor.services.auth.jwt_service import (
    InvalidTokenError,
    verify_token,
)
from indusia_visual_editor.services.auth.user_crud import get_user_by_id


def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing Authorization header",
        )
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="malformed Authorization header",
        )
    return parts[1].strip()


async def get_current_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
    config: AppConfig = Depends(get_config),
) -> User:
    token = _extract_bearer(authorization)
    try:
        payload = verify_token(
            token,
            secret=config.auth_jwt_secret,
            algorithm=config.auth_jwt_algorithm,
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid token: {exc}",
        ) from exc

    if payload.token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="access token required",
        )

    user = await get_user_by_id(session, payload.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user no longer exists",
        )
    return user


async def get_current_user_optional(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
    config: AppConfig = Depends(get_config),
) -> User | None:
    """Same as `get_current_user` but returns None instead of raising 401
    when the request is unauthenticated. Use on public-but-scopable GETs
    (e.g. listing projects): logged-in callers get an org-scoped view, the
    unauthenticated dashboard still loads with the legacy unscoped view."""
    if authorization is None:
        return None
    try:
        return await get_current_user(
            authorization=authorization, session=session, config=config
        )
    except HTTPException:
        return None


def require_role(*allowed: str):
    """Factory: returns a FastAPI dependency that enforces `allowed` roles."""

    async def _enforce(current_user: User = Depends(get_current_user)) -> User:
        role_value = (
            current_user.role.value
            if hasattr(current_user.role, "value")
            else str(current_user.role)
        )
        if role_value not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"role {role_value!r} not permitted",
            )
        return current_user

    return _enforce
