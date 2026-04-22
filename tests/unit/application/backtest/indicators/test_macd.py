"""MACD: line = fast_EMA - slow_EMA."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.application.backtest.indicators.ema import ExponentialMovingAverage
from cryptozavr.application.backtest.indicators.macd import MACD
from tests.unit.application.backtest.indicators.fixtures import candle


def test_warm_up_returns_none_until_slow_period() -> None:
    macd = MACD(fast=2, slow=4)
    for i in range(3):
        assert macd.update(candle(i, close=str(100 + i))) is None
    assert macd.is_warm is False


def test_line_equals_fast_ema_minus_slow_ema() -> None:
    """Run a parallel fast EMA + slow EMA and confirm the MACD line
    matches their difference once both are warm."""
    macd = MACD(fast=2, slow=4)
    fast_ref = ExponentialMovingAverage(period=2)
    slow_ref = ExponentialMovingAverage(period=4)

    closes_raw = ("100", "101", "103", "102", "105", "104", "107")
    for i, c in enumerate(closes_raw):
        macd_val = macd.update(candle(i, close=c))
        fast_val = fast_ref.update(candle(i, close=c))
        slow_val = slow_ref.update(candle(i, close=c))
        if macd_val is None:
            assert slow_val is None
        else:
            assert fast_val is not None
            assert slow_val is not None
            assert macd_val == fast_val - slow_val


def test_constant_input_gives_zero_line() -> None:
    """Both EMAs converge to the constant input ⇒ MACD line = 0."""
    macd = MACD(fast=2, slow=4)
    for i in range(20):
        result = macd.update(candle(i, close="100"))
    assert result == Decimal("0")


def test_fast_must_be_less_than_slow() -> None:
    with pytest.raises(ValueError, match="fast must be < slow"):
        MACD(fast=10, slow=10)
    with pytest.raises(ValueError, match="fast must be < slow"):
        MACD(fast=20, slow=10)


def test_nonpositive_periods_raise() -> None:
    with pytest.raises(ValueError, match="fast/slow must be > 0"):
        MACD(fast=0, slow=10)
    with pytest.raises(ValueError, match="fast/slow must be > 0"):
        MACD(fast=5, slow=0)
