"""Ticker upsert → load roundtrip via SupabaseGateway."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.domain.market_data import Ticker
from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.symbols import Symbol, SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Percentage
from cryptozavr.domain.venues import MarketType, VenueId

pytestmark = pytest.mark.integration


async def _ensure_btc_symbol_registered(
    supabase_pool,
    registry: SymbolRegistry,
) -> Symbol:
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


def _quality() -> DataQuality:
    return DataQuality(
        source=Provenance(venue_id="kucoin", endpoint="fetch_ticker"),
        fetched_at=Instant.now(),
        staleness=Staleness.FRESH,
        confidence=Confidence.HIGH,
        cache_hit=False,
    )


async def test_ticker_upsert_then_load(
    supabase_gateway,
    supabase_pool,
    clean_market_data,
) -> None:
    registry = supabase_gateway._registry
    symbol = await _ensure_btc_symbol_registered(supabase_pool, registry)
    observed = Instant.from_ms(1_745_200_800_000)
    ticker = Ticker(
        symbol=symbol,
        last=Decimal("65000.5"),
        bid=Decimal("64999.5"),
        ask=Decimal("65001.5"),
        volume_24h=Decimal("1234"),
        change_24h_pct=Percentage(value=Decimal("2.5")),
        high_24h=Decimal("66000"),
        low_24h=Decimal("64000"),
        observed_at=observed,
        quality=_quality(),
    )
    await supabase_gateway.upsert_ticker(ticker)
    loaded = await supabase_gateway.load_ticker(symbol)
    assert loaded is not None
    assert loaded.last == Decimal("65000.5")
    assert loaded.bid == Decimal("64999.5")
    assert loaded.ask == Decimal("65001.5")
    assert loaded.change_24h_pct is not None
    assert loaded.change_24h_pct.value == Decimal("2.5")


async def test_ticker_upsert_overwrites(
    supabase_gateway,
    supabase_pool,
    clean_market_data,
) -> None:
    registry = supabase_gateway._registry
    symbol = await _ensure_btc_symbol_registered(supabase_pool, registry)
    observed = Instant.from_ms(1_745_200_800_000)
    first = Ticker(
        symbol=symbol,
        last=Decimal("60000"),
        observed_at=observed,
        quality=_quality(),
    )
    second = Ticker(
        symbol=symbol,
        last=Decimal("65000"),
        observed_at=observed,
        quality=_quality(),
    )
    await supabase_gateway.upsert_ticker(first)
    await supabase_gateway.upsert_ticker(second)
    loaded = await supabase_gateway.load_ticker(symbol)
    assert loaded is not None
    assert loaded.last == Decimal("65000")
