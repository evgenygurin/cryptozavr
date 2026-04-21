"""OHLCV upsert → load roundtrip via SupabaseGateway."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.domain.market_data import OHLCVCandle, OHLCVSeries
from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.symbols import Symbol, SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Timeframe, TimeRange
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


def _fresh_quality() -> DataQuality:
    return DataQuality(
        source=Provenance(venue_id="kucoin", endpoint="fetch_ohlcv"),
        fetched_at=Instant.now(),
        staleness=Staleness.FRESH,
        confidence=Confidence.HIGH,
        cache_hit=False,
    )


def _make_series(symbol: Symbol, count: int) -> OHLCVSeries:
    tf = Timeframe.H1
    step_ms = tf.to_milliseconds()
    base_ms = 1_745_200_800_000
    candles = tuple(
        OHLCVCandle(
            opened_at=Instant.from_ms(base_ms + i * step_ms),
            open=Decimal("100") + Decimal(i),
            high=Decimal("110") + Decimal(i),
            low=Decimal("90") + Decimal(i),
            close=Decimal("105") + Decimal(i),
            volume=Decimal("1000"),
            closed=True,
        )
        for i in range(count)
    )
    return OHLCVSeries(
        symbol=symbol,
        timeframe=tf,
        candles=candles,
        range=TimeRange(
            start=candles[0].opened_at,
            end=Instant.from_ms(candles[-1].opened_at.to_ms() + step_ms),
        ),
        quality=_fresh_quality(),
    )


async def test_ohlcv_upsert_then_load_roundtrip(
    supabase_gateway,
    supabase_pool,
    clean_market_data,
) -> None:
    registry = supabase_gateway._registry
    symbol = await _ensure_btc_symbol_registered(supabase_pool, registry)

    series = _make_series(symbol, count=5)
    written = await supabase_gateway.upsert_ohlcv(series)
    assert written == 5

    loaded = await supabase_gateway.load_ohlcv(symbol, Timeframe.H1, limit=100)
    assert loaded is not None
    assert len(loaded.candles) == 5
    assert loaded.candles[0].open == Decimal("100")
    assert loaded.candles[-1].close == Decimal("109")


async def test_ohlcv_upsert_is_idempotent(
    supabase_gateway,
    supabase_pool,
    clean_market_data,
) -> None:
    registry = supabase_gateway._registry
    symbol = await _ensure_btc_symbol_registered(supabase_pool, registry)
    series = _make_series(symbol, count=3)
    await supabase_gateway.upsert_ohlcv(series)
    await supabase_gateway.upsert_ohlcv(series)
    loaded = await supabase_gateway.load_ohlcv(symbol, Timeframe.H1, limit=100)
    assert loaded is not None
    assert len(loaded.candles) == 3


async def test_load_ohlcv_empty_returns_none(
    supabase_gateway,
    supabase_pool,
    clean_market_data,
) -> None:
    registry = supabase_gateway._registry
    symbol = await _ensure_btc_symbol_registered(supabase_pool, registry)
    loaded = await supabase_gateway.load_ohlcv(symbol, Timeframe.H1, limit=100)
    assert loaded is None
