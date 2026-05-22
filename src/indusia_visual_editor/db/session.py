"""Async SQLAlchemy engine + session factory.

A single engine is cached per process via lru_cache; the FastAPI dependency
`get_session` yields a fresh AsyncSession per request and ensures rollback +
close on exit.
"""

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from indusia_visual_editor.config import get_config


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    config = get_config()
    if not config.database_url:
        raise RuntimeError(
            "IVE_DATABASE_URL not set. Start docker-compose.dev.yml postgres or "
            "export the DSN to use the database layer."
        )
    return create_async_engine(
        config.database_url,
        echo=False,
        future=True,
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        get_engine(),
        expire_on_commit=False,
        class_=AsyncSession,
    )


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency. Yields a session and guarantees rollback on error."""
    factory = get_sessionmaker()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
