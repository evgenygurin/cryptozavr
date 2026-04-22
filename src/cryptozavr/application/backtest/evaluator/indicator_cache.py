"""IndicatorCache: intern IndicatorRef -> Indicator with prev-value snapshot.

The same `IndicatorRef` appearing in entry + exit produces one stream,
so entry and exit agree on the current value bar-for-bar. After each
`tick(candle)`, current values snapshot into previous so crossing ops
can see both.
"""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.backtest.indicators.base import Indicator
from cryptozavr.application.backtest.indicators.factory import create_indicator
from cryptozavr.application.strategy.strategy_spec import IndicatorRef
from cryptozavr.domain.market_data import OHLCVCandle


class IndicatorCache:
    def __init__(self) -> None:
        self._indicators: dict[IndicatorRef, Indicator] = {}
        self._current: dict[IndicatorRef, Decimal | None] = {}
        self._previous: dict[IndicatorRef, Decimal | None] = {}

    def register(self, ref: IndicatorRef) -> None:
        """Idempotent: registering the same ref twice is a no-op."""
        if ref not in self._indicators:
            self._indicators[ref] = create_indicator(ref)
            self._current[ref] = None
            self._previous[ref] = None

    def tick(self, candle: OHLCVCandle) -> None:
        for ref, ind in self._indicators.items():
            self._previous[ref] = self._current[ref]
            self._current[ref] = ind.update(candle)

    def current_value(self, ref: IndicatorRef) -> Decimal | None:
        if ref not in self._indicators:
            raise KeyError(f"IndicatorRef {ref} not registered in cache")
        return self._current[ref]

    def previous_value(self, ref: IndicatorRef) -> Decimal | None:
        if ref not in self._indicators:
            raise KeyError(f"IndicatorRef {ref} not registered in cache")
        return self._previous[ref]

    def all_warm(self) -> bool:
        return all(v is not None for v in self._current.values())
