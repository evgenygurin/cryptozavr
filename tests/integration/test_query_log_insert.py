"""Insert-only audit trail: query_log."""

from __future__ import annotations

import pytest

from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Timeframe
from cryptozavr.domain.venues import MarketType, VenueId

pytestmark = pytest.mark.integration


async def _ensure_btc_symbol_registered(
    supabase_pool,
    registry: SymbolRegistry,
):
    async with supabase_pool.acquire() as conn:
        await conn.execute(
            """
            insert into cryptozavr.symbols
              (venue_id, base, quote, market_type, native_symbol, active)
            values ('kucoin', 'BTC', 'USDT', 'spot', 'BTC-USDT', true)
            on conflict (venue_id, base, quote, market_type) do nothing
            """
        )
    return registry.get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )


async def test_insert_query_log_returns_uuid(
    supabase_gateway,
    supabase_pool,
) -> None:
    registry = supabase_gateway._registry
    symbol = await _ensure_btc_symbol_registered(supabase_pool, registry)

    query_id = await supabase_gateway.insert_query_log(
        kind="ohlcv",
        symbol=symbol,
        timeframe=Timeframe.H1,
        range_start=Instant.from_ms(1_745_200_800_000),
        range_end=Instant.from_ms(1_745_287_200_000),
        limit_n=500,
        force_refresh=False,
        reason_codes=("venue:healthy", "cache:miss"),
        quality=None,
        issued_by="mcp_tool:get_ohlcv",
        client_id="session-abc",
    )
    assert query_id is not None

    async with supabase_pool.acquire() as conn:
        row = await conn.fetchrow(
            "select kind, issued_by, client_id, reason_codes "
            "  from cryptozavr.query_log where id = $1",
            query_id,
        )
    assert row is not None
    assert row["kind"] == "ohlcv"
    assert row["issued_by"] == "mcp_tool:get_ohlcv"
    assert row["client_id"] == "session-abc"
    assert list(row["reason_codes"]) == ["venue:healthy", "cache:miss"]


async def test_insert_query_log_without_symbol(
    supabase_gateway,
) -> None:
    query_id = await supabase_gateway.insert_query_log(
        kind="discovery",
        symbol=None,
        timeframe=None,
        range_start=None,
        range_end=None,
        limit_n=None,
        force_refresh=False,
        reason_codes=(),
        quality=None,
        issued_by="mcp_tool:list_trending",
        client_id=None,
    )
    assert query_id is not None
