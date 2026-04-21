"""Test VolatilityRegimeStrategy: ATR + regime classification."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.strategies.volatility import (
    VolatilityRegimeStrategy,
)
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


def _c(t: int, o: str, h: str, low: str, c: str) -> OHLCVCandle:
    return OHLCVCandle(
        opened_at=Instant.from_ms(t),
        open=Decimal(o),
        high=Decimal(h),
        low=Decimal(low),
        close=Decimal(c),
        volume=Decimal("1"),
    )


class TestVolatilityRegimeStrategy:
    def test_name_is_volatility_regime(self) -> None:
        assert VolatilityRegimeStrategy().name == "volatility_regime"

    def test_tight_candles_classify_as_calm(self) -> None:
        # high-low = 0.5 on close=100 → TR≈0.5, TR%≈0.5 — calm (<1)
        candles = tuple(_c(i * 60_000, "100", "100.25", "99.75", "100") for i in range(15))
        result = VolatilityRegimeStrategy(window=14).analyze(_make_series(candles))
        assert result.findings["regime"] == "calm"
        assert result.findings["atr"] is not None
        assert result.findings["atr_pct"] < Decimal("1")

    def test_wide_candles_classify_as_high(self) -> None:
        # high-low = 5 on close=100 → TR%=5 — high (3-6)
        candles = tuple(_c(i * 60_000, "100", "102.5", "97.5", "100") for i in range(15))
        result = VolatilityRegimeStrategy(window=14).analyze(_make_series(candles))
        assert result.findings["regime"] == "high"
        assert result.findings["atr_pct"] >= Decimal("3")
        assert result.findings["atr_pct"] < Decimal("6")

    def test_extremely_wide_candles_classify_as_extreme(self) -> None:
        candles = tuple(_c(i * 60_000, "100", "105", "95", "100") for i in range(15))
        result = VolatilityRegimeStrategy(window=14).analyze(_make_series(candles))
        assert result.findings["regime"] == "extreme"
        assert result.findings["atr_pct"] >= Decimal("6")

    def test_too_few_bars_yields_low_confidence(self) -> None:
        candles = tuple(_c(i * 60_000, "100", "101", "99", "100") for i in range(5))
        result = VolatilityRegimeStrategy(window=14).analyze(_make_series(candles))
        assert result.confidence is Confidence.LOW
        assert result.findings["atr"] is None
        assert result.findings["regime"] == "unknown"
