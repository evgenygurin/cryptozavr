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

LOCAL_DB_URL = os.environ.get(
    "SUPABASE_DB_URL",
    "postgresql://postgres:postgres@127.0.0.1:54322/postgres",
)


async def _is_supabase_reachable(dsn: str) -> bool:
    try:
        conn = await asyncpg.connect(dsn, timeout=2)
        await conn.close()
        return True
    except Exception:
        return False


@pytest_asyncio.fixture(scope="session")
async def supabase_pool() -> AsyncIterator[asyncpg.Pool]:
    """Session-scoped pool against local Supabase; skip if unreachable."""
    if not await _is_supabase_reachable(LOCAL_DB_URL):
        pytest.skip("Supabase not reachable at " + LOCAL_DB_URL + " — run `supabase start` first.")
    pool = await create_pool(PgPoolConfig(dsn=LOCAL_DB_URL, min_size=1, max_size=5))
    yield pool
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
