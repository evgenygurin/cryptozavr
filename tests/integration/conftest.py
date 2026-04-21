"""Fixtures for integration tests (require `supabase start` locally + Docker)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio

from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.infrastructure.supabase.gateway import SupabaseGateway
from cryptozavr.infrastructure.supabase.pg_pool import PgPoolConfig, create_pool

_LOCAL_DB_URL_DEFAULT = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"


def _db_url() -> str:
    """Resolve the Supabase DB URL at fixture-time, not import-time.

    Integration tests run with env injected after the test process starts,
    so reading os.environ here picks up SUPABASE_DB_URL when it's set and
    falls back to the local Supabase default otherwise.
    """
    return os.environ.get("SUPABASE_DB_URL", _LOCAL_DB_URL_DEFAULT)


async def _is_supabase_reachable(dsn: str) -> bool:
    try:
        conn = await asyncpg.connect(dsn, timeout=2)
        await conn.close()
        return True
    except Exception:
        return False


@pytest_asyncio.fixture
async def supabase_pool() -> AsyncIterator[asyncpg.Pool]:
    """Function-scoped pool; skip if unreachable.

    Function scope avoids the "attached to a different loop" error that
    pytest-asyncio raises when a session-scoped async fixture tries to
    outlive a function-scoped event loop.
    """
    dsn = _db_url()
    if not await _is_supabase_reachable(dsn):
        pytest.skip(
            f"Supabase not reachable at {dsn} — set SUPABASE_DB_URL or run `supabase start`."
        )
    pool = await create_pool(PgPoolConfig(dsn=dsn, min_size=1, max_size=5))
    try:
        yield pool
    finally:
        await pool.close()


@pytest_asyncio.fixture
async def supabase_gateway(
    supabase_pool: asyncpg.Pool,
) -> AsyncIterator[SupabaseGateway]:
    """Gateway wired to the live local Supabase stack."""
    registry = SymbolRegistry()
    gw = SupabaseGateway(supabase_pool, registry)
    yield gw


@pytest_asyncio.fixture
async def clean_market_data(supabase_pool: asyncpg.Pool) -> AsyncIterator[None]:
    """Truncate market-data tables before each test."""
    async with supabase_pool.acquire() as conn:
        await conn.execute(
            "truncate table cryptozavr.tickers_live, "
            "cryptozavr.ohlcv_candles, "
            "cryptozavr.orderbook_snapshots, "
            "cryptozavr.trades "
            "restart identity cascade"
        )
    yield
