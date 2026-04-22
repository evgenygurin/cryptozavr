"""SimpleMovingAverage: rolling sum over the last N closes."""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cryptozavr.application.backtest.indicators.sma import SimpleMovingAverage
from cryptozavr.application.strategy.enums import PriceSource
from tests.unit.application.backtest.indicators.fixtures import candle, closes


def test_warm_up_returns_none_until_window_full() -> None:
    sma = SimpleMovingAverage(period=3)
    bars = closes(("10", "20"))
    for bar in bars:
        assert sma.update(bar) is None
    assert sma.is_warm is False


def test_first_warm_value_matches_plain_mean() -> None:
    sma = SimpleMovingAverage(period=3)
    bars = closes(("10", "20", "30"))
    result = None
    for bar in bars:
        result = sma.update(bar)
    assert result == Decimal("20")
    assert sma.is_warm is True


def test_window_rolls_on_subsequent_bars() -> None:
    """After the window is full, new bars replace the oldest one."""
    sma = SimpleMovingAverage(period=3)
    bars = closes(("10", "20", "30", "40"))
    values = [sma.update(b) for b in bars]
    # After bar 4: window is (20, 30, 40), mean = 30
    assert values[-1] == Decimal("30")


def test_period_one_emits_latest_every_bar() -> None:
    sma = SimpleMovingAverage(period=1)
    assert sma.update(candle(0, close="50")) == Decimal("50")
    assert sma.update(candle(1, close="55")) == Decimal("55")


def test_uses_source_field() -> None:
    sma = SimpleMovingAverage(period=2, source=PriceSource.HIGH)
    sma.update(candle(0, high="100"))
    result = sma.update(candle(1, high="200"))
    assert result == Decimal("150")


def test_period_zero_raises() -> None:
    with pytest.raises(ValueError, match="period must be > 0"):
        SimpleMovingAverage(period=0)


def test_period_negative_raises() -> None:
    with pytest.raises(ValueError, match="period must be > 0"):
        SimpleMovingAverage(period=-1)


@given(
    st.lists(
        st.decimals(
            min_value="1",
            max_value="1000000",
            allow_nan=False,
            allow_infinity=False,
            places=2,
        ),
        min_size=5,
        max_size=30,
    )
)
def test_property_matches_naive_mean_over_window(values: list[Decimal]) -> None:
    """Rolling SMA matches the naive sliding-window mean within a tight
    relative tolerance. Running-sum incremental subtraction can shift
    the last Decimal digit vs. re-summing each bar, so we compare with
    1e-20 tolerance instead of exact equality."""
    period = 3
    sma = SimpleMovingAverage(period=period)
    for i, v in enumerate(values):
        result = sma.update(candle(i, close=str(v)))
        if i < period - 1:
            assert result is None
        else:
            expected = sum(values[i - period + 1 : i + 1], Decimal("0")) / Decimal(period)
            assert result is not None
            assert abs(result - expected) < Decimal("1e-20")
