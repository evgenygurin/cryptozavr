from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.application.backtest.simulator.position import OpenPosition
from cryptozavr.application.strategy.enums import StrategySide


def test_open_position_construction() -> None:
    pos = OpenPosition(
        side=StrategySide.LONG,
        entry_price=Decimal("100"),
        size=Decimal("1.5"),
        entry_bar_index=5,
        take_profit_level=Decimal("105"),
        stop_loss_level=Decimal("98"),
    )
    assert pos.side is StrategySide.LONG
    assert pos.size == Decimal("1.5")


def test_open_position_is_frozen() -> None:
    pos = OpenPosition(
        side=StrategySide.LONG,
        entry_price=Decimal("100"),
        size=Decimal("1"),
        entry_bar_index=0,
        take_profit_level=None,
        stop_loss_level=None,
    )
    with pytest.raises((AttributeError, Exception)):
        pos.size = Decimal("2")  # type: ignore[misc]
