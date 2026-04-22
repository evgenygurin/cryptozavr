"""Condition: lhs indicator op {indicator|decimal constant}."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from cryptozavr.application.strategy.enums import (
    ComparatorOp,
    IndicatorKind,
)
from cryptozavr.application.strategy.strategy_spec import Condition, IndicatorRef


def _ind(kind: IndicatorKind = IndicatorKind.SMA, period: int = 20) -> IndicatorRef:
    return IndicatorRef(kind=kind, period=period)


def test_condition_with_two_indicators() -> None:
    c = Condition(
        lhs=_ind(IndicatorKind.EMA, 12),
        op=ComparatorOp.GT,
        rhs=_ind(IndicatorKind.EMA, 26),
    )
    assert c.op is ComparatorOp.GT
    assert isinstance(c.rhs, IndicatorRef)


def test_condition_with_decimal_constant() -> None:
    c = Condition(lhs=_ind(IndicatorKind.RSI, 14), op=ComparatorOp.LT, rhs=Decimal("30"))
    assert c.rhs == Decimal("30")


def test_condition_rejects_nan_rhs() -> None:
    with pytest.raises(ValidationError):
        Condition(lhs=_ind(), op=ComparatorOp.GT, rhs=Decimal("NaN"))


def test_condition_is_frozen() -> None:
    c = Condition(lhs=_ind(), op=ComparatorOp.GT, rhs=Decimal("100"))
    with pytest.raises(ValidationError):
        c.op = ComparatorOp.LT  # type: ignore[misc]
