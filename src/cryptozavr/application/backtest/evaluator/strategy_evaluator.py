"""StrategyEvaluator.tick(bar_index) -> SignalTick.

Entry conditions AND-folded; exit conditions OR-folded. Either fold
returns None if any contributing condition is None (warm-up propagates).
Zero exit conditions emit exit_signal=False (not None) once at least
one entry is past warm-up - so the simulator can still act on TP/SL.
"""

from __future__ import annotations

import pandas as pd

from cryptozavr.application.backtest.evaluator.condition import evaluate_condition
from cryptozavr.application.backtest.evaluator.signals import SignalTick
from cryptozavr.application.strategy.strategy_spec import (
    IndicatorRef,
    StrategySpec,
)


def _fold_and(signals: list[bool | None]) -> bool | None:
    if any(s is None for s in signals):
        return None
    return all(s for s in signals if s is not None)


def _fold_or(signals: list[bool | None]) -> bool | None:
    if any(s is None for s in signals):
        return None
    return any(s for s in signals if s is not None)


class StrategyEvaluator:
    def __init__(
        self,
        spec: StrategySpec,
        series_map: dict[IndicatorRef, pd.Series],
    ) -> None:
        self._spec = spec
        self._series = series_map

    def tick(self, bar_index: int) -> SignalTick:
        entry_results = [
            evaluate_condition(c, self._series, bar_index) for c in self._spec.entry.conditions
        ]
        entry_signal = _fold_and(entry_results)
        if self._spec.exit.conditions:
            exit_results = [
                evaluate_condition(c, self._series, bar_index) for c in self._spec.exit.conditions
            ]
            exit_signal: bool | None = _fold_or(exit_results)
        else:
            # TP/SL-only exit: explicit False lets simulator act on TP/SL
            # without misreading a None as "still warming".
            exit_signal = False
        return SignalTick(
            bar_index=bar_index,
            entry_signal=entry_signal,
            exit_signal=exit_signal,
        )
