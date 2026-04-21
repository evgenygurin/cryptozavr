"""Test SupportResistanceStrategy: swing-pivot SR detection."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.strategies.support_resistance import (
    SupportResistanceStrategy,
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


def _c(t: int, h: str, low: str) -> OHLCVCandle:
    mid = (Decimal(h) + Decimal(low)) / Decimal(2)
    return OHLCVCandle(
        opened_at=Instant.from_ms(t),
        open=mid,
        high=Decimal(h),
        low=Decimal(low),
        close=mid,
        volume=Decimal("1"),
    )


class TestSupportResistanceStrategy:
    def test_name_is_support_resistance(self) -> None:
        assert SupportResistanceStrategy().name == "support_resistance"

    def test_detects_obvious_pivot_high_and_low(self) -> None:
        # valley at i=2 (low 90), peak at i=5 (high 120)
        series = _make_series(
            (
                _c(0, "110", "100"),
                _c(60_000, "105", "95"),
                _c(120_000, "100", "90"),  # pivot low
                _c(180_000, "108", "98"),
                _c(240_000, "115", "105"),
                _c(300_000, "120", "110"),  # pivot high
                _c(360_000, "118", "108"),
                _c(420_000, "112", "102"),
            )
        )
        result = SupportResistanceStrategy(window=2).analyze(series)
        assert Decimal("90") in result.findings["supports"]
        assert Decimal("120") in result.findings["resistances"]

    def test_clusters_nearby_levels(self) -> None:
        # two pivot highs within 0.5% → collapse to one
        series = _make_series(
            (
                _c(0, "100", "95"),
                _c(60_000, "105", "100"),
                _c(120_000, "120", "110"),  # pivot high ~120
                _c(180_000, "118", "108"),
                _c(240_000, "120.3", "110"),  # within 0.5% of 120
                _c(300_000, "115", "105"),
                _c(360_000, "110", "100"),
            )
        )
        result = SupportResistanceStrategy(
            window=2,
            cluster_pct=Decimal("0.5"),
        ).analyze(series)
        resistances = result.findings["resistances"]
        near_120 = [r for r in resistances if Decimal("119") <= r <= Decimal("121")]
        assert len(near_120) == 1

    def test_too_few_bars_for_window_yields_low_confidence(self) -> None:
        # window=2 needs 2*2+1=5 bars minimum
        series = _make_series(
            (
                _c(0, "110", "100"),
                _c(60_000, "105", "95"),
                _c(120_000, "100", "90"),
            )
        )
        result = SupportResistanceStrategy(window=2).analyze(series)
        assert result.confidence is Confidence.LOW
        assert result.findings["supports"] == ()
        assert result.findings["resistances"] == ()
