"""StrategyExit: OR-conjunction of conditions + optional TP/SL."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from cryptozavr.application.strategy.enums import (
    ComparatorOp,
    IndicatorKind,
)
from cryptozavr.application.strategy.strategy_spec import (
    Condition,
    IndicatorRef,
    StrategyExit,
)


def _c() -> Condition:
    return Condition(
        lhs=IndicatorRef(kind=IndicatorKind.SMA, period=20),
        op=ComparatorOp.LT,
        rhs=Decimal("100"),
    )


def test_exit_with_conditions_only() -> None:
    ex = StrategyExit(conditions=(_c(),))
    assert ex.take_profit_pct is None
    assert ex.stop_loss_pct is None


def test_exit_with_tp_sl_only() -> None:
    ex = StrategyExit(
        conditions=(),
        take_profit_pct=Decimal("0.05"),
        stop_loss_pct=Decimal("0.02"),
    )
    assert ex.take_profit_pct == Decimal("0.05")


def test_exit_requires_at_least_one_bail_out() -> None:
    with pytest.raises(ValidationError):
        StrategyExit(conditions=(), take_profit_pct=None, stop_loss_pct=None)


def test_negative_take_profit_rejected() -> None:
    with pytest.raises(ValidationError):
        StrategyExit(conditions=(_c(),), take_profit_pct=Decimal("-0.05"))


def test_negative_stop_loss_rejected() -> None:
    with pytest.raises(ValidationError):
        StrategyExit(conditions=(_c(),), stop_loss_pct=Decimal("-0.02"))
