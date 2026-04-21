"""Smoke: all cryptozavr tables + cron jobs exist after `supabase db push`."""

from __future__ import annotations

import pytest
import pytest_asyncio

pytestmark = pytest.mark.integration


EXPECTED_TABLES = {
    "assets",
    "ohlcv_candles",
    "orderbook_snapshots",
    "provider_events",
    "query_log",
    "symbol_aliases",
    "symbols",
    "tickers_live",
    "trades",
    "venues",
}

EXPECTED_CRON_JOBS = {"prune-stale-tickers", "prune-query-log"}


@pytest_asyncio.fixture
async def db_conn(supabase_pool):
    async with supabase_pool.acquire() as conn:
        yield conn


async def test_all_tables_exist(db_conn) -> None:
    rows = await db_conn.fetch(
        "select table_name from information_schema.tables "
        "where table_schema = 'cryptozavr' order by table_name"
    )
    actual = {r["table_name"] for r in rows}
    assert EXPECTED_TABLES.issubset(actual), f"missing tables: {EXPECTED_TABLES - actual}"


async def test_rls_enabled_on_all_tables(db_conn) -> None:
    rows = await db_conn.fetch(
        "select c.relname from pg_class c "
        "join pg_namespace n on n.oid = c.relnamespace "
        "where n.nspname = 'cryptozavr' and c.relkind = 'r' and c.relrowsecurity"
    )
    actual = {r["relname"] for r in rows}
    assert EXPECTED_TABLES.issubset(actual), f"tables without RLS: {EXPECTED_TABLES - actual}"


async def test_cron_jobs_registered(db_conn) -> None:
    rows = await db_conn.fetch("select jobname from cron.job order by jobname")
    actual = {r["jobname"] for r in rows}
    assert EXPECTED_CRON_JOBS.issubset(actual), f"missing cron jobs: {EXPECTED_CRON_JOBS - actual}"


async def test_seed_venues_present(db_conn) -> None:
    rows = await db_conn.fetch("select id from cryptozavr.venues order by id")
    ids = {r["id"] for r in rows}
    assert "kucoin" in ids
    assert "coingecko" in ids
