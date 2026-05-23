"""Auth routes: signup, login, refresh, current-user introspection.

Login mints both an access token (returned in the JSON body) and a refresh
token (set as HttpOnly cookie). Refresh exchanges the cookie for a fresh
access token without re-prompting the operator. /me returns the current
user so the Vue layer can render the navbar without parsing the JWT itself.

Wrong-credentials and unknown-email paths return the same 401 + opaque
message so a probe cannot enumerate registered emails.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from indusia_visual_editor.config import AppConfig, get_config
from indusia_visual_editor.db.models import User
from indusia_visual_editor.db.session import get_session
from indusia_visual_editor.schemas.auth import (
    LoginRequest,
    SignupRequest,
    TokenResponse,
    UserRead,
)
from indusia_visual_editor.services.auth.dependencies import get_current_user
from indusia_visual_editor.services.auth.jwt_service import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    verify_token,
)
from indusia_visual_editor.services.auth.passwords import verify_password
from indusia_visual_editor.services.auth.user_crud import (
    DuplicateEmailError,
    create_user,
    get_user_by_email,
    get_user_by_id,
)
from indusia_visual_editor.utils.responses import failed, success

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _token_response(user: User, config: AppConfig) -> dict:
    access = create_access_token(
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
        secret=config.auth_jwt_secret,
        algorithm=config.auth_jwt_algorithm,
        ttl_seconds=config.auth_jwt_ttl_seconds,
    )
    payload = TokenResponse(
        access_token=access,
        token_type="Bearer",
        expires_in=config.auth_jwt_ttl_seconds,
        user=UserRead.model_validate(user),
    )
    return payload.model_dump(mode="json")


def _attach_refresh_cookie(
    response: JSONResponse, user: User, config: AppConfig
) -> JSONResponse:
    """Set the HttpOnly refresh cookie on the JSONResponse returned by the
    success() helper. Must be applied AFTER `success()` builds the response —
    FastAPI does not merge `Response` parameter cookies into a fresh
    JSONResponse the handler returns."""
    refresh = create_refresh_token(
        user_id=user.id,
        organization_id=user.organization_id,
        secret=config.auth_jwt_secret,
        algorithm=config.auth_jwt_algorithm,
        ttl_seconds=config.auth_refresh_ttl_seconds,
    )
    response.set_cookie(
        key=config.auth_refresh_cookie_name,
        value=refresh,
        max_age=config.auth_refresh_ttl_seconds,
        httponly=True,
        secure=config.auth_refresh_cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup_route(
    payload: SignupRequest,
    session: AsyncSession = Depends(get_session),
    config: AppConfig = Depends(get_config),
):
    try:
        user = await create_user(
            session,
            email=payload.email,
            plaintext_password=payload.password,
            organization_slug=payload.organization_slug,
        )
    except DuplicateEmailError:
        return failed("email already registered", status_code=409)

    body = _token_response(user, config)
    response = success(
        data=body,
        message="account created",
        status_code=status.HTTP_201_CREATED,
    )
    return _attach_refresh_cookie(response, user, config)


@router.post("/login")
async def login_route(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_session),
    config: AppConfig = Depends(get_config),
):
    user = await get_user_by_email(session, payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        return failed("invalid credentials", status_code=401)

    body = _token_response(user, config)
    response = success(data=body, message="logged in")
    return _attach_refresh_cookie(response, user, config)


@router.post("/refresh")
async def refresh_route(
    request: Request,
    session: AsyncSession = Depends(get_session),
    config: AppConfig = Depends(get_config),
):
    token = request.cookies.get(config.auth_refresh_cookie_name)
    if not token:
        return failed("missing refresh cookie", status_code=401)
    try:
        payload = verify_token(
            token,
            secret=config.auth_jwt_secret,
            algorithm=config.auth_jwt_algorithm,
        )
    except InvalidTokenError:
        return failed("invalid refresh token", status_code=401)
    if payload.token_type != "refresh":
        return failed("wrong token type", status_code=401)

    user = await get_user_by_id(session, payload.user_id)
    if user is None:
        return failed("user no longer exists", status_code=401)

    body = _token_response(user, config)
    response = success(data=body, message="token refreshed")
    return _attach_refresh_cookie(response, user, config)


@router.post("/logout")
async def logout_route(
    config: AppConfig = Depends(get_config),
):
    response = success(message="logged out")
    response.delete_cookie(key=config.auth_refresh_cookie_name, path="/")
    return response


@router.get("/me")
async def me_route(current_user: User = Depends(get_current_user)):
    return success(data=UserRead.model_validate(current_user).model_dump(mode="json"))
