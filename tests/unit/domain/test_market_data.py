"""Test market data entities."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.domain.market_data import OHLCVCandle, OHLCVSeries, Ticker, TradeSide
from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.symbols import Symbol, SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Percentage, Timeframe, TimeRange
from cryptozavr.domain.venues import MarketType, VenueId


@pytest.fixture
def registry() -> SymbolRegistry:
    return SymbolRegistry()


@pytest.fixture
def btc_usdt(registry: SymbolRegistry) -> Symbol:
    return registry.get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )


@pytest.fixture
def fresh_quality() -> DataQuality:
    return DataQuality(
        source=Provenance(venue_id="kucoin", endpoint="fetch_ticker"),
        fetched_at=Instant.now(),
        staleness=Staleness.FRESH,
        confidence=Confidence.HIGH,
        cache_hit=False,
    )


class TestTradeSide:
    def test_values(self) -> None:
        assert TradeSide.BUY.value == "buy"
        assert TradeSide.SELL.value == "sell"
        assert TradeSide.UNKNOWN.value == "unknown"


class TestTicker:
    def test_happy_path(self, btc_usdt: Symbol, fresh_quality: DataQuality) -> None:
        t = Ticker(
            symbol=btc_usdt,
            last=Decimal("65000.50"),
            bid=Decimal("64999.50"),
            ask=Decimal("65001.50"),
            volume_24h=Decimal("1234.56"),
            change_24h_pct=Percentage(value=Decimal("2.5")),
            high_24h=Decimal("66000"),
            low_24h=Decimal("64000"),
            observed_at=Instant.now(),
            quality=fresh_quality,
        )
        assert t.last == Decimal("65000.50")
        assert t.bid == Decimal("64999.50")

    def test_minimal(self, btc_usdt: Symbol, fresh_quality: DataQuality) -> None:
        t = Ticker(
            symbol=btc_usdt,
            last=Decimal("65000"),
            observed_at=Instant.now(),
            quality=fresh_quality,
        )
        assert t.bid is None
        assert t.ask is None
        assert t.volume_24h is None


def _make_candles(start_ms: int, count: int, tf_ms: int) -> tuple[OHLCVCandle, ...]:
    return tuple(
        OHLCVCandle(
            opened_at=Instant.from_ms(start_ms + i * tf_ms),
            open=Decimal("100"),
            high=Decimal("110"),
            low=Decimal("90"),
            close=Decimal("105"),
            volume=Decimal("1000"),
            closed=True,
        )
        for i in range(count)
    )


class TestOHLCVCandle:
    def test_happy_path(self) -> None:
        c = OHLCVCandle(
            opened_at=Instant.from_ms(1000),
            open=Decimal("100"),
            high=Decimal("110"),
            low=Decimal("90"),
            close=Decimal("105"),
            volume=Decimal("1000"),
            closed=True,
        )
        assert c.high == Decimal("110")


class TestOHLCVSeries:
    def test_happy_path(self, btc_usdt: Symbol, fresh_quality: DataQuality) -> None:
        candles = _make_candles(start_ms=0, count=5, tf_ms=Timeframe.H1.to_milliseconds())
        series = OHLCVSeries(
            symbol=btc_usdt,
            timeframe=Timeframe.H1,
            candles=candles,
            range=TimeRange(start=candles[0].opened_at, end=Instant.from_ms(5 * 3_600_000)),
            quality=fresh_quality,
        )
        assert len(series.candles) == 5

    def test_last_returns_last_candle(self, btc_usdt: Symbol, fresh_quality: DataQuality) -> None:
        candles = _make_candles(start_ms=0, count=3, tf_ms=Timeframe.H1.to_milliseconds())
        series = OHLCVSeries(
            symbol=btc_usdt,
            timeframe=Timeframe.H1,
            candles=candles,
            range=TimeRange(start=candles[0].opened_at, end=Instant.from_ms(3 * 3_600_000)),
            quality=fresh_quality,
        )
        assert series.last() is candles[-1]

    def test_window_returns_last_n(self, btc_usdt: Symbol, fresh_quality: DataQuality) -> None:
        candles = _make_candles(start_ms=0, count=10, tf_ms=Timeframe.H1.to_milliseconds())
        series = OHLCVSeries(
            symbol=btc_usdt,
            timeframe=Timeframe.H1,
            candles=candles,
            range=TimeRange(start=candles[0].opened_at, end=Instant.from_ms(10 * 3_600_000)),
            quality=fresh_quality,
        )
        windowed = series.window(3)
        assert len(windowed.candles) == 3
        assert windowed.candles[-1] is candles[-1]

    def test_slice_by_time_range(self, btc_usdt: Symbol, fresh_quality: DataQuality) -> None:
        candles = _make_candles(start_ms=0, count=10, tf_ms=Timeframe.H1.to_milliseconds())
        series = OHLCVSeries(
            symbol=btc_usdt,
            timeframe=Timeframe.H1,
            candles=candles,
            range=TimeRange(start=candles[0].opened_at, end=Instant.from_ms(10 * 3_600_000)),
            quality=fresh_quality,
        )
        sliced = series.slice(
            TimeRange(
                start=Instant.from_ms(2 * 3_600_000),
                end=Instant.from_ms(5 * 3_600_000),
            )
        )
        assert len(sliced.candles) == 3
        assert sliced.candles[0].opened_at == Instant.from_ms(2 * 3_600_000)

    def test_empty_series_last_raises(self, btc_usdt: Symbol, fresh_quality: DataQuality) -> None:
        series = OHLCVSeries(
            symbol=btc_usdt,
            timeframe=Timeframe.H1,
            candles=(),
            range=TimeRange(start=Instant.from_ms(0), end=Instant.from_ms(1)),
            quality=fresh_quality,
        )
        with pytest.raises(IndexError):
            series.last()
