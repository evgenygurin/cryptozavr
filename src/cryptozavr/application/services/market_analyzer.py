"""MarketAnalyzer — Strategy context over AnalysisStrategy registry."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from cryptozavr.application.strategies.base import (
    AnalysisResult,
    AnalysisStrategy,
)
from cryptozavr.domain.market_data import OHLCVSeries
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Timeframe


@dataclass(frozen=True, slots=True)
class AnalysisReport:
    """Aggregated output of MarketAnalyzer.analyze()."""

    symbol: Symbol
    timeframe: Timeframe
    results: tuple[AnalysisResult, ...]


class MarketAnalyzer:
    """Dispatches to registered AnalysisStrategy by name.

    The strategy registry is injected at construction. Consumers request
    strategies by name in `strategy_names`; the analyzer runs them in
    order and wraps results in an AnalysisReport.
    """

    def __init__(self, strategies: Mapping[str, AnalysisStrategy]) -> None:
        self._strategies: Mapping[str, AnalysisStrategy] = dict(strategies)

    def analyze(
        self,
        *,
        series: OHLCVSeries,
        strategy_names: tuple[str, ...],
    ) -> AnalysisReport:
        results: list[AnalysisResult] = []
        for name in strategy_names:
            strategy = self._strategies[name]  # raises KeyError if missing
            results.append(strategy.analyze(series))
        return AnalysisReport(
            symbol=series.symbol,
            timeframe=series.timeframe,
            results=tuple(results),
        )
