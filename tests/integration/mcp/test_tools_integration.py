"""End-to-end integration tests for the get_ticker / get_ohlcv MCP tools.

Skip-safe: requires a running local Supabase with migrations applied and all
SUPABASE_* env vars configured.  Uses the live FastMCP lifespan + real
httpx/ccxt providers.
"""

from __future__ import annotations

import os

import asyncpg
import pytest
from fastmcp import Client

from cryptozavr.mcp.server import build_server
from cryptozavr.mcp.settings import Settings

pytestmark = pytest.mark.integration

_REQUIRED_ENV_VARS = (
    "SUPABASE_DB_URL",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
)

_LOCAL_DB_URL = os.environ.get(
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


@pytest.fixture(autouse=True)
async def _skip_if_no_supabase() -> None:
    """Skip when SUPABASE env vars aren't configured or Supabase is unreachable."""
    missing = [v for v in _REQUIRED_ENV_VARS if not os.getenv(v)]
    if missing:
        pytest.skip(f"Missing env vars: {', '.join(missing)} — skipping live integration tests")
    if not await _is_supabase_reachable(_LOCAL_DB_URL):
        pytest.skip(f"Supabase not reachable at {_LOCAL_DB_URL} — run `supabase start` first.")


@pytest.fixture
def settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


async def test_get_ticker_full_stack_against_live_supabase(
    settings: Settings,
) -> None:
    mcp = build_server(settings)
    async with Client(mcp) as client:
        # First call — should miss cache and hit the provider.
        first = await client.call_tool(
            "get_ticker",
            {"venue": "kucoin", "symbol": "BTC-USDT"},
        )
        assert first.structured_content["venue"] == "kucoin"
        assert first.structured_content["symbol"] == "BTC-USDT"
        assert "provider:called" in first.structured_content["reason_codes"]

        # Second call within TTL — may or may not hit cache depending on
        # in-memory decorator TTL; we only assert it returns a ticker.
        second = await client.call_tool(
            "get_ticker",
            {"venue": "kucoin", "symbol": "BTC-USDT"},
        )
        assert second.structured_content["symbol"] == "BTC-USDT"


async def test_get_ohlcv_full_stack_against_live_supabase(
    settings: Settings,
) -> None:
    mcp = build_server(settings)
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_ohlcv",
            {
                "venue": "kucoin",
                "symbol": "BTC-USDT",
                "timeframe": "1m",
                "limit": 10,
            },
        )
    payload = result.structured_content
    assert payload["venue"] == "kucoin"
    assert payload["symbol"] == "BTC-USDT"
    assert payload["timeframe"] == "1m"
    assert len(payload["candles"]) >= 1
    assert "provider:called" in payload["reason_codes"]
