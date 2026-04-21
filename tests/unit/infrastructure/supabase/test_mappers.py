"""Test pure row-to-Domain mappers."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.symbols import Symbol, SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Timeframe
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.supabase.mappers import (
    row_to_ohlcv_candle,
    row_to_ohlcv_series,
    row_to_symbol,
    row_to_ticker,
)


@pytest.fixture
def registry() -> SymbolRegistry:
    return SymbolRegistry()


@pytest.fixture
def btc_symbol(registry: SymbolRegistry) -> Symbol:
    return registry.get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )


def _fresh_quality() -> DataQuality:
    return DataQuality(
        source=Provenance(venue_id="kucoin", endpoint="fetch_ticker"),
        fetched_at=Instant.now(),
        staleness=Staleness.FRESH,
        confidence=Confidence.HIGH,
        cache_hit=True,
    )


class TestRowToSymbol:
    def test_happy_path(self, registry: SymbolRegistry) -> None:
        row = {
            "id": 42,
            "venue_id": "kucoin",
            "base": "BTC",
            "quote": "USDT",
            "market_type": "spot",
            "native_symbol": "BTC-USDT",
            "active": True,
        }
        sym = row_to_symbol(row, registry)
        assert sym.venue == VenueId.KUCOIN
        assert sym.base == "BTC"
        assert sym.quote == "USDT"
        assert sym.market_type == MarketType.SPOT
        assert sym.native_symbol == "BTC-USDT"

    def test_reuses_registry_instance(self, registry: SymbolRegistry, btc_symbol: Symbol) -> None:
        row = {
            "id": 42,
            "venue_id": "kucoin",
            "base": "BTC",
            "quote": "USDT",
            "market_type": "spot",
            "native_symbol": "BTC-USDT",
            "active": True,
        }
        sym = row_to_symbol(row, registry)
        assert sym is btc_symbol


class TestRowToTicker:
    def test_full_row(self, btc_symbol: Symbol) -> None:
        observed = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)
        row = {
            "symbol_id": 42,
            "last": Decimal("65000.50"),
            "bid": Decimal("64999.50"),
            "ask": Decimal("65001.50"),
            "volume_24h": Decimal("1234.56"),
            "change_24h_pct": Decimal("2.5"),
            "high_24h": Decimal("66000"),
            "low_24h": Decimal("64000"),
            "observed_at": observed,
            "fetched_at": observed,
            "source_endpoint": "fetch_ticker",
        }
        ticker = row_to_ticker(row, symbol=btc_symbol, quality=_fresh_quality())
        assert ticker.last == Decimal("65000.50")
        assert ticker.bid == Decimal("64999.50")
        assert ticker.ask == Decimal("65001.50")
        assert ticker.volume_24h == Decimal("1234.56")
        assert ticker.change_24h_pct is not None
        assert ticker.change_24h_pct.value == Decimal("2.5")
        assert ticker.observed_at == Instant(observed)

    def test_minimal_row(self, btc_symbol: Symbol) -> None:
        observed = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)
        row = {
            "symbol_id": 42,
            "last": Decimal("65000"),
            "bid": None,
            "ask": None,
            "volume_24h": None,
            "change_24h_pct": None,
            "high_24h": None,
            "low_24h": None,
            "observed_at": observed,
            "fetched_at": observed,
            "source_endpoint": "fetch_ticker",
        }
        ticker = row_to_ticker(row, symbol=btc_symbol, quality=_fresh_quality())
        assert ticker.last == Decimal("65000")
        assert ticker.bid is None


class TestRowToOhlcvCandle:
    def test_happy_path(self) -> None:
        opened = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)
        row = {
            "opened_at": opened,
            "open": Decimal("100"),
            "high": Decimal("110"),
            "low": Decimal("90"),
            "close": Decimal("105"),
            "volume": Decimal("1000"),
            "closed": True,
        }
        candle = row_to_ohlcv_candle(row)
        assert candle.opened_at == Instant(opened)
        assert candle.open == Decimal("100")
        assert candle.high == Decimal("110")
        assert candle.low == Decimal("90")
        assert candle.close == Decimal("105")
        assert candle.volume == Decimal("1000")
        assert candle.closed is True


class TestRowToOhlcvSeries:
    def test_happy_path(self, btc_symbol: Symbol) -> None:
        rows = [
            {
                "opened_at": datetime(2026, 4, 21, 10 + i, 0, 0, tzinfo=UTC),
                "open": Decimal("100"),
                "high": Decimal("110"),
                "low": Decimal("90"),
                "close": Decimal("105"),
                "volume": Decimal("1000"),
                "closed": True,
            }
            for i in range(3)
        ]
        series = row_to_ohlcv_series(
            rows,
            symbol=btc_symbol,
            timeframe=Timeframe.H1,
            quality=_fresh_quality(),
        )
        assert len(series.candles) == 3
        assert series.timeframe == Timeframe.H1
        assert series.symbol is btc_symbol

    def test_empty_rows_raises(self, btc_symbol: Symbol) -> None:
        with pytest.raises(ValueError, match="at least one row"):
            row_to_ohlcv_series(
                [],
                symbol=btc_symbol,
                timeframe=Timeframe.H1,
                quality=_fresh_quality(),
            )
