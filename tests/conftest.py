"""Shared pytest fixtures.

The DB engine in `db.session` is lru_cached for prod efficiency, but pytest-
asyncio creates a fresh event loop per test (Python 3.14 + pytest-asyncio
0.24 defaults). A cached AsyncEngine bound to test #1's loop is dead in
test #2 → `RuntimeError: Event loop is closed`. Drop the caches between
tests so each test gets a fresh engine on its own loop.

Phase 13.3 added a bearer-token gate on every mutation endpoint. Updating
every existing route test to mint a token would explode the diff. Instead
this conftest installs a FastAPI dependency override that resolves
`get_current_user` to a synthetic engineer-role User, EXCEPT for tests in
the auth_* modules which exercise the gate itself and need the real
behaviour.
"""

import uuid

import pytest

from indusia_visual_editor.db import session as db_session
from indusia_visual_editor.db.models import User, UserRole
from indusia_visual_editor.main import app
from indusia_visual_editor.services.auth.dependencies import get_current_user
from indusia_visual_editor.services.auth.user_crud import SEED_ORG_ID


_AUTH_TEST_MODULES = {
    "tests.routes.test_auth",
    "tests.routes.test_auth_middleware",
    "tests.services.auth.test_jwt",
    "tests.services.auth.test_passwords",
    "tests.services.auth.test_rbac",
}


def _synthetic_user() -> User:
    """Fake operator that the dependency override returns. Detached from
    the session — tests that need a real DB-resident user should call the
    signup endpoint instead. Role is admin so legacy tests can exercise
    every gated mutation; role-specific behaviour is verified explicitly
    in tests/services/auth/test_rbac.py with per-test overrides."""
    return User(
        id=uuid.UUID("00000000-0000-0000-0000-00000000aaaa"),
        organization_id=SEED_ORG_ID,
        email="test-user@indusiatest.dev",
        password_hash="not-a-real-hash",
        role=UserRole.ADMIN,
    )


@pytest.fixture(autouse=True)
def _override_auth_for_legacy_tests(request: pytest.FixtureRequest):
    """Auto-bypass the bearer gate for non-auth route tests so the existing
    backend suite (~290 tests) keeps green without per-test token plumbing.
    Auth + middleware modules opt out by module path."""
    module_path = request.node.module.__name__
    if module_path in _AUTH_TEST_MODULES:
        yield
        return
    app.dependency_overrides[get_current_user] = _synthetic_user
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(autouse=True)
async def _reset_db_engine_cache():
    db_session.get_engine.cache_clear()
    db_session.get_sessionmaker.cache_clear()
    yield
    engine = db_session.get_engine.__wrapped__ if hasattr(db_session.get_engine, "__wrapped__") else None
    # Best-effort dispose of any engine the test created, then reset for next test.
    try:
        cached_engine = db_session.get_engine.cache_info().currsize and db_session.get_engine()
    except Exception:
        cached_engine = None
    if cached_engine is not None:
        try:
            await cached_engine.dispose()
        except Exception:
            pass
    db_session.get_engine.cache_clear()
    db_session.get_sessionmaker.cache_clear()
