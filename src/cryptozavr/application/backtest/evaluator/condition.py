"""evaluate_condition: Condition + IndicatorCache -> bool | None.

None is returned whenever any indicator involved in the comparison is
still warming up, or when a crossing op has no previous value yet.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from cryptozavr.application.backtest.evaluator.indicator_cache import IndicatorCache
from cryptozavr.application.strategy.enums import ComparatorOp
from cryptozavr.application.strategy.strategy_spec import Condition, IndicatorRef


def _resolve_current(side: IndicatorRef | Decimal, cache: IndicatorCache) -> Decimal | None:
    if isinstance(side, Decimal):
        return side
    return cache.current_value(side)


def _resolve_previous(side: IndicatorRef | Decimal, cache: IndicatorCache) -> Decimal | None:
    if isinstance(side, Decimal):
        # Constants are "always the same" — their "previous" is themselves.
        return side
    return cache.previous_value(side)


# Simple-comparison dispatch keeps the return-count down (ruff PLR0911)
# and makes the op semantics trivially auditable.
_SIMPLE_OPS: dict[ComparatorOp, Callable[[Decimal, Decimal], bool]] = {
    ComparatorOp.GT: lambda a, b: a > b,
    ComparatorOp.GTE: lambda a, b: a >= b,
    ComparatorOp.LT: lambda a, b: a < b,
    ComparatorOp.LTE: lambda a, b: a <= b,
}


def evaluate_condition(condition: Condition, cache: IndicatorCache) -> bool | None:
    curr_lhs = _resolve_current(condition.lhs, cache)
    curr_rhs = _resolve_current(condition.rhs, cache)
    if curr_lhs is None or curr_rhs is None:
        return None
    op = condition.op
    simple = _SIMPLE_OPS.get(op)
    if simple is not None:
        return simple(curr_lhs, curr_rhs)
    # Crossing ops require previous bar values.
    prev_lhs = _resolve_previous(condition.lhs, cache)
    prev_rhs = _resolve_previous(condition.rhs, cache)
    if prev_lhs is None or prev_rhs is None:
        return None
    if op is ComparatorOp.CROSSES_ABOVE:
        return prev_lhs <= prev_rhs and curr_lhs > curr_rhs
    if op is ComparatorOp.CROSSES_BELOW:
        return prev_lhs >= prev_rhs and curr_lhs < curr_rhs
    # Exhaustiveness — adding a ComparatorOp without extending this fn
    # would bypass type-check; raise to surface the gap at runtime too.
    raise ValueError(f"unhandled ComparatorOp: {op!r}")
