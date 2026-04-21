"""Test MarketAnalyzer: dispatches to registered AnalysisStrategy by name."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.application.services.market_analyzer import (
    AnalysisReport,
    MarketAnalyzer,
)
from cryptozavr.application.strategies.base import AnalysisResult
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


def _series() -> OHLCVSeries:
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
    candles = (
        OHLCVCandle(
            opened_at=Instant.from_ms(0),
            open=Decimal("100"),
            high=Decimal("110"),
            low=Decimal("90"),
            close=Decimal("105"),
            volume=Decimal("10"),
        ),
    )
    return OHLCVSeries(
        symbol=symbol,
        timeframe=Timeframe.M1,
        candles=candles,
        range=TimeRange(
            start=Instant.from_ms(0),
            end=Instant.from_ms(60_000),
        ),
        quality=quality,
    )


class _FakeStrategy:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls = 0

    def analyze(self, series: OHLCVSeries) -> AnalysisResult:
        self.calls += 1
        return AnalysisResult(
            strategy=self.name,
            findings={"ran": True},
            confidence=Confidence.HIGH,
        )


class TestMarketAnalyzer:
    def test_dispatch_to_single_registered_strategy(self) -> None:
        strat = _FakeStrategy("volatility")
        analyzer = MarketAnalyzer(strategies={"volatility": strat})
        report = analyzer.analyze(
            series=_series(),
            strategy_names=("volatility",),
        )
        assert isinstance(report, AnalysisReport)
        assert strat.calls == 1
        assert len(report.results) == 1
        assert report.results[0].strategy == "volatility"
        assert report.symbol.native_symbol == "BTC-USDT"

    def test_dispatch_multiple_strategies_preserves_order(self) -> None:
        s1, s2 = _FakeStrategy("a"), _FakeStrategy("b")
        analyzer = MarketAnalyzer(strategies={"a": s1, "b": s2})
        report = analyzer.analyze(
            series=_series(),
            strategy_names=("b", "a"),
        )
        assert [r.strategy for r in report.results] == ["b", "a"]

    def test_unknown_strategy_raises(self) -> None:
        analyzer = MarketAnalyzer(strategies={"a": _FakeStrategy("a")})
        with pytest.raises(KeyError):
            analyzer.analyze(series=_series(), strategy_names=("missing",))
