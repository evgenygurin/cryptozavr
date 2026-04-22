from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.application.backtest.simulator.fees import FixedBpsFeeModel


def test_five_bps_on_notional() -> None:
    m = FixedBpsFeeModel(bps=5)  # 0.0005
    assert m.compute(notional=Decimal("10000"), is_entry=True) == Decimal("5")


def test_zero_bps_is_zero_fee() -> None:
    assert FixedBpsFeeModel(bps=0).compute(notional=Decimal("10000"), is_entry=True) == Decimal("0")


def test_entry_and_exit_use_same_bps() -> None:
    m = FixedBpsFeeModel(bps=10)  # 0.001
    assert m.compute(notional=Decimal("1000"), is_entry=True) == Decimal("1")
    assert m.compute(notional=Decimal("1000"), is_entry=False) == Decimal("1")


def test_negative_bps_raises() -> None:
    with pytest.raises(ValueError, match="bps must be >= 0"):
        FixedBpsFeeModel(bps=-1)


def test_zero_notional_is_zero_fee() -> None:
    assert FixedBpsFeeModel(bps=5).compute(notional=Decimal("0"), is_entry=True) == Decimal("0")
