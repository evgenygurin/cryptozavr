"""evaluate_condition: read pre-computed series at bar_index, apply op.

Returns None when:
- Any referenced IndicatorRef has NaN at bar_index (warming up).
- A crossing op has no previous bar (bar_index == 0) or NaN in previous.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from decimal import Decimal

import pandas as pd

from cryptozavr.application.strategy.enums import ComparatorOp
from cryptozavr.application.strategy.strategy_spec import Condition, IndicatorRef


def _current_value(
    side: IndicatorRef | Decimal,
    series_map: dict[IndicatorRef, pd.Series],
    bar_index: int,
) -> float | None:
    if isinstance(side, Decimal):
        return float(side)
    v = series_map[side].iloc[bar_index]
    if isinstance(v, float) and math.isnan(v):
        return None
    return float(v)


def _previous_value(
    side: IndicatorRef | Decimal,
    series_map: dict[IndicatorRef, pd.Series],
    bar_index: int,
) -> float | None:
    if bar_index == 0:
        return float(side) if isinstance(side, Decimal) else None
    if isinstance(side, Decimal):
        return float(side)
    v = series_map[side].iloc[bar_index - 1]
    if isinstance(v, float) and math.isnan(v):
        return None
    return float(v)


_SIMPLE_OPS: dict[ComparatorOp, Callable[[float, float], bool]] = {
    ComparatorOp.GT: lambda a, b: a > b,
    ComparatorOp.GTE: lambda a, b: a >= b,
    ComparatorOp.LT: lambda a, b: a < b,
    ComparatorOp.LTE: lambda a, b: a <= b,
}


def evaluate_condition(
    condition: Condition,
    series_map: dict[IndicatorRef, pd.Series],
    bar_index: int,
) -> bool | None:
    curr_lhs = _current_value(condition.lhs, series_map, bar_index)
    curr_rhs = _current_value(condition.rhs, series_map, bar_index)
    if curr_lhs is None or curr_rhs is None:
        return None
    op = condition.op
    simple = _SIMPLE_OPS.get(op)
    if simple is not None:
        return simple(curr_lhs, curr_rhs)
    prev_lhs = _previous_value(condition.lhs, series_map, bar_index)
    prev_rhs = _previous_value(condition.rhs, series_map, bar_index)
    if prev_lhs is None or prev_rhs is None:
        return None
    if op is ComparatorOp.CROSSES_ABOVE:
        return prev_lhs <= prev_rhs and curr_lhs > curr_rhs
    if op is ComparatorOp.CROSSES_BELOW:
        return prev_lhs >= prev_rhs and curr_lhs < curr_rhs
    raise ValueError(f"unhandled ComparatorOp: {op!r}")
