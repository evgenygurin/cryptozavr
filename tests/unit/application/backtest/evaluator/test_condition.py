"""evaluate_condition: all 6 ComparatorOps, None-propagation on NaN."""

from __future__ import annotations

from decimal import Decimal

import pandas as pd

from cryptozavr.application.backtest.evaluator.condition import evaluate_condition
from cryptozavr.application.strategy.enums import ComparatorOp, IndicatorKind
from cryptozavr.application.strategy.strategy_spec import Condition, IndicatorRef

_REF_A = IndicatorRef(kind=IndicatorKind.SMA, period=1)
_REF_B = IndicatorRef(kind=IndicatorKind.SMA, period=2)


def _series_map(a: list[float], b: list[float] | None = None) -> dict:
    sm: dict = {_REF_A: pd.Series(a, dtype="float64")}
    if b is not None:
        sm[_REF_B] = pd.Series(b, dtype="float64")
    return sm


def test_gt_true() -> None:
    cond = Condition(lhs=_REF_A, op=ComparatorOp.GT, rhs=Decimal("50"))
    assert evaluate_condition(cond, _series_map([100.0]), 0) is True


def test_gt_false() -> None:
    cond = Condition(lhs=_REF_A, op=ComparatorOp.GT, rhs=Decimal("50"))
    assert evaluate_condition(cond, _series_map([10.0]), 0) is False


def test_gte_equal() -> None:
    cond = Condition(lhs=_REF_A, op=ComparatorOp.GTE, rhs=Decimal("50"))
    assert evaluate_condition(cond, _series_map([50.0]), 0) is True


def test_lt_true() -> None:
    cond = Condition(lhs=_REF_A, op=ComparatorOp.LT, rhs=Decimal("50"))
    assert evaluate_condition(cond, _series_map([10.0]), 0) is True


def test_lte_equal() -> None:
    cond = Condition(lhs=_REF_A, op=ComparatorOp.LTE, rhs=Decimal("50"))
    assert evaluate_condition(cond, _series_map([50.0]), 0) is True


def test_crosses_above_true_on_crossing_bar() -> None:
    cond = Condition(lhs=_REF_A, op=ComparatorOp.CROSSES_ABOVE, rhs=Decimal("50"))
    # prev=40, curr=60 -> crosses above 50
    assert evaluate_condition(cond, _series_map([40.0, 60.0]), 1) is True


def test_crosses_above_false_when_both_above() -> None:
    cond = Condition(lhs=_REF_A, op=ComparatorOp.CROSSES_ABOVE, rhs=Decimal("50"))
    assert evaluate_condition(cond, _series_map([60.0, 70.0]), 1) is False


def test_crosses_below_true() -> None:
    cond = Condition(lhs=_REF_A, op=ComparatorOp.CROSSES_BELOW, rhs=Decimal("50"))
    assert evaluate_condition(cond, _series_map([60.0, 40.0]), 1) is True


def test_crosses_op_none_on_bar_zero() -> None:
    cond = Condition(lhs=_REF_A, op=ComparatorOp.CROSSES_ABOVE, rhs=Decimal("50"))
    # bar 0: no previous value available
    assert evaluate_condition(cond, _series_map([40.0]), 0) is None


def test_none_on_nan_lhs() -> None:
    cond = Condition(lhs=_REF_A, op=ComparatorOp.GT, rhs=Decimal("50"))
    assert evaluate_condition(cond, _series_map([float("nan")]), 0) is None


def test_indicator_vs_indicator() -> None:
    cond = Condition(lhs=_REF_A, op=ComparatorOp.GTE, rhs=_REF_B)
    assert evaluate_condition(cond, _series_map([100.0], [100.0]), 0) is True
    assert evaluate_condition(cond, _series_map([50.0], [100.0]), 0) is False


def test_equal_then_cross_fires() -> None:
    """prev_lhs == prev_rhs AND curr_lhs > curr_rhs -> CROSSES_ABOVE True
    (canonical `<=` left side)."""
    cond = Condition(lhs=_REF_A, op=ComparatorOp.CROSSES_ABOVE, rhs=Decimal("50"))
    assert evaluate_condition(cond, _series_map([50.0, 51.0]), 1) is True


def test_nan_in_previous_returns_none_for_crossing() -> None:
    cond = Condition(lhs=_REF_A, op=ComparatorOp.CROSSES_ABOVE, rhs=Decimal("50"))
    assert evaluate_condition(cond, _series_map([float("nan"), 60.0]), 1) is None
