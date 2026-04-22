"""StrategyEntry: side + AND-conjunction of conditions."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from cryptozavr.application.strategy.enums import (
    ComparatorOp,
    IndicatorKind,
    StrategySide,
)
from cryptozavr.application.strategy.strategy_spec import (
    Condition,
    IndicatorRef,
    StrategyEntry,
)


def _c() -> Condition:
    return Condition(
        lhs=IndicatorRef(kind=IndicatorKind.SMA, period=20),
        op=ComparatorOp.GT,
        rhs=Decimal("100"),
    )


def test_minimal_long_entry() -> None:
    entry = StrategyEntry(side=StrategySide.LONG, conditions=(_c(),))
    assert entry.side is StrategySide.LONG
    assert len(entry.conditions) == 1


def test_empty_conditions_rejected() -> None:
    with pytest.raises(ValidationError):
        StrategyEntry(side=StrategySide.LONG, conditions=())


def test_more_than_eight_conditions_rejected() -> None:
    with pytest.raises(ValidationError):
        StrategyEntry(
            side=StrategySide.LONG,
            conditions=tuple(_c() for _ in range(9)),
        )
