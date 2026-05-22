"""Phase 0.4 sanity check: confirm the dev Postgres in docker-compose.dev.yml
is reachable from the test process using SQLAlchemy 2.x async + asyncpg.

This test does NOT exercise any application code (no models, no sessions) —
it only verifies that the DSN in `.env`/env vars points at a live Postgres
that accepts our credentials. It is skipped when IVE_DATABASE_URL is unset so
CI without Docker doesn't fail; the local dev workflow requires it pass.
"""

import os

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


DB_URL = os.environ.get("IVE_DATABASE_URL")


@pytest.mark.skipif(
    not DB_URL,
    reason="IVE_DATABASE_URL not set; start docker-compose.dev.yml postgres first.",
)
@pytest.mark.asyncio
async def test_can_connect_to_postgres():
    engine = create_async_engine(DB_URL, echo=False, future=True)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            value = result.scalar_one()
            assert value == 1
            version_row = await conn.execute(text("SHOW server_version"))
            version = version_row.scalar_one()
            assert version.startswith("16."), f"expected Postgres 16, got {version}"
    finally:
        await engine.dispose()
