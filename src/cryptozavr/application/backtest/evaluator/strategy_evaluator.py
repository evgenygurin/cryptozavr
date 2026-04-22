"""StrategyEvaluator: per-bar entry/exit signals for a StrategySpec.

Construction pre-registers every IndicatorRef reachable through the spec
so each `tick()` is O(num_conditions) rather than rescanning the spec.
"""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.backtest.evaluator.condition import evaluate_condition
from cryptozavr.application.backtest.evaluator.indicator_cache import IndicatorCache
from cryptozavr.application.backtest.evaluator.signals import SignalTick
from cryptozavr.application.strategy.strategy_spec import (
    Condition,
    IndicatorRef,
    StrategySpec,
)
from cryptozavr.domain.market_data import OHLCVCandle


def _iter_refs(conditions: tuple[Condition, ...]) -> list[IndicatorRef]:
    refs: list[IndicatorRef] = []
    for c in conditions:
        refs.append(c.lhs)
        if isinstance(c.rhs, IndicatorRef):
            refs.append(c.rhs)
        # Decimal RHS doesn't need cache registration.
        else:
            _ = c.rhs  # touch to keep type checker happy about narrowing
    return refs


def _fold_and(signals: list[bool | None]) -> bool | None:
    """AND-fold with None propagation: any None wins; else all-True."""
    if any(s is None for s in signals):
        return None
    # After the None-filter, all elements are bool.
    return all(s for s in signals if s is not None)


def _fold_or(signals: list[bool | None]) -> bool | None:
    """OR-fold with None propagation: any None wins; else any-True."""
    if any(s is None for s in signals):
        return None
    return any(s for s in signals if s is not None)


class StrategyEvaluator:
    def __init__(self, spec: StrategySpec) -> None:
        self._spec = spec
        self._cache = IndicatorCache()
        self._bar_index = -1
        # Pre-register every ref from entry + exit.
        for ref in (
            *_iter_refs(spec.entry.conditions),
            *_iter_refs(spec.exit.conditions),
        ):
            self._cache.register(ref)

    @property
    def is_warm(self) -> bool:
        return self._cache.all_warm()

    @property
    def indicator_cache(self) -> IndicatorCache:
        """Exposed for 2B.3 so the trade simulator can peek at raw
        indicator values (e.g. ATR-based stop-loss)."""
        return self._cache

    def tick(self, candle: OHLCVCandle) -> SignalTick:
        self._bar_index += 1
        self._cache.tick(candle)
        entry_results = [evaluate_condition(c, self._cache) for c in self._spec.entry.conditions]
        exit_results = [evaluate_condition(c, self._cache) for c in self._spec.exit.conditions]
        # Exit may have zero conditions (all bail-outs are TP/SL) — an
        # empty list of exit conditions means "no condition-based exit",
        # which is a *false* exit signal, not None.
        exit_signal: bool | None
        exit_signal = False if not self._spec.exit.conditions else _fold_or(exit_results)
        return SignalTick(
            bar_index=self._bar_index,
            entry_signal=_fold_and(entry_results),
            exit_signal=exit_signal,
        )


__all__ = [
    "Decimal",  # re-exported for callers that reuse our Decimal import
    "IndicatorCache",
    "SignalTick",
    "StrategyEvaluator",
    "evaluate_condition",
]
