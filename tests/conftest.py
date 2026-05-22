"""Shared pytest fixtures.

The DB engine in `db.session` is lru_cached for prod efficiency, but pytest-
asyncio creates a fresh event loop per test (Python 3.14 + pytest-asyncio
0.24 defaults). A cached AsyncEngine bound to test #1's loop is dead in
test #2 → `RuntimeError: Event loop is closed`. Drop the caches between
tests so each test gets a fresh engine on its own loop.
"""

import pytest

from indusia_visual_editor.db import session as db_session


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
