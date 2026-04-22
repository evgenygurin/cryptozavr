from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.application.backtest.simulator.slippage import PctSlippageModel
from cryptozavr.application.strategy.enums import StrategySide


def test_long_entry_adds_slippage() -> None:
    m = PctSlippageModel(bps=10)  # 10 bps = 0.001
    fill = m.adjust(reference=Decimal("100"), side=StrategySide.LONG, is_entry=True)
    assert fill == Decimal("100.1")


def test_long_exit_subtracts_slippage() -> None:
    m = PctSlippageModel(bps=10)
    fill = m.adjust(reference=Decimal("100"), side=StrategySide.LONG, is_entry=False)
    assert fill == Decimal("99.9")


def test_short_entry_subtracts_slippage() -> None:
    m = PctSlippageModel(bps=10)
    fill = m.adjust(reference=Decimal("100"), side=StrategySide.SHORT, is_entry=True)
    assert fill == Decimal("99.9")


def test_short_exit_adds_slippage() -> None:
    m = PctSlippageModel(bps=10)
    fill = m.adjust(reference=Decimal("100"), side=StrategySide.SHORT, is_entry=False)
    assert fill == Decimal("100.1")


def test_zero_bps_is_noop() -> None:
    m = PctSlippageModel(bps=0)
    fill = m.adjust(reference=Decimal("100"), side=StrategySide.LONG, is_entry=True)
    assert fill == Decimal("100")


def test_negative_bps_raises() -> None:
    with pytest.raises(ValueError, match="bps must be >= 0"):
        PctSlippageModel(bps=-1)
