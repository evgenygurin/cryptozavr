"""Test VwapStrategy: volume-weighted average price."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.strategies.vwap import VwapStrategy
from cryptozavr.domain.market_data import OHLCVCandle, OHLCVSeries
from cryptozavr.domain.quality import (
    Confidence,
    DataQuality,
    Provenance,
    Staleness,
)
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Timeframe, TimeRange
from cryptozavr.domain.venues import MarketType, VenueId


def _make_series(candles: tuple[OHLCVCandle, ...]) -> OHLCVSeries:
    symbol = SymbolRegistry().get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )
    quality = DataQuality(
        source=Provenance(venue_id="kucoin", endpoint="fetch_ohlcv"),
        fetched_at=Instant.from_ms(1_700_000_000_000),
        staleness=Staleness.FRESH,
        confidence=Confidence.HIGH,
        cache_hit=False,
    )
    if candles:
        tr = TimeRange(
            start=candles[0].opened_at,
            end=Instant.from_ms(candles[-1].opened_at.to_ms() + 60_000),
        )
    else:
        tr = TimeRange(start=Instant.from_ms(0), end=Instant.from_ms(60_000))
    return OHLCVSeries(
        symbol=symbol,
        timeframe=Timeframe.M1,
        candles=candles,
        range=tr,
        quality=quality,
    )


def _candle(t: int, o: str, h: str, low: str, c: str, v: str) -> OHLCVCandle:
    return OHLCVCandle(
        opened_at=Instant.from_ms(t),
        open=Decimal(o),
        high=Decimal(h),
        low=Decimal(low),
        close=Decimal(c),
        volume=Decimal(v),
    )


class TestVwapStrategy:
    def test_name_is_vwap(self) -> None:
        assert VwapStrategy().name == "vwap"

    def test_single_candle_vwap_equals_typical_price(self) -> None:
        series = _make_series((_candle(0, "100", "110", "90", "105", "10"),))
        result = VwapStrategy().analyze(series)
        typical = (Decimal("110") + Decimal("90") + Decimal("105")) / Decimal(3)
        assert result.findings["vwap"] == typical
        assert result.findings["total_volume"] == Decimal("10")
        assert result.findings["bars_used"] == 1

    def test_weighted_by_volume(self) -> None:
        # candle1 typical=100, vol=1 → 100; candle2 typical=200, vol=9 → 1800
        # total=10, weighted=1900, vwap=190
        series = _make_series(
            (
                _candle(0, "100", "100", "100", "100", "1"),
                _candle(60_000, "200", "200", "200", "200", "9"),
            )
        )
        result = VwapStrategy().analyze(series)
        assert result.findings["vwap"] == Decimal("190")
        assert result.findings["total_volume"] == Decimal("10")
        assert result.findings["bars_used"] == 2

    def test_empty_series_yields_low_confidence_and_none_vwap(self) -> None:
        series = _make_series(())
        result = VwapStrategy().analyze(series)
        assert result.findings["vwap"] is None
        assert result.findings["total_volume"] == Decimal("0")
        assert result.findings["bars_used"] == 0
        assert result.confidence is Confidence.LOW

    def test_zero_volume_candles_skipped_but_bars_counted(self) -> None:
        series = _make_series(
            (
                _candle(0, "100", "100", "100", "100", "0"),
                _candle(60_000, "200", "200", "200", "200", "10"),
            )
        )
        result = VwapStrategy().analyze(series)
        assert result.findings["vwap"] == Decimal("200")
        assert result.findings["total_volume"] == Decimal("10")
        assert result.findings["bars_used"] == 2
