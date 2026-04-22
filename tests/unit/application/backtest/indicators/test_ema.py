"""ExponentialMovingAverage: SMA-seeded + alpha recurrence, vectorized."""

from __future__ import annotations

import math

import pytest

from cryptozavr.application.backtest.indicators.ema import (
    ExponentialMovingAverage,
)
from tests.unit.application.backtest.fixtures import candle_df


def test_warm_up_returns_nan_until_period_bars() -> None:
    ema = ExponentialMovingAverage(period=3)
    series = ema.compute(candle_df(["10", "20"]))
    assert math.isnan(series.iloc[0])
    assert math.isnan(series.iloc[1])


def test_first_warm_value_is_sma_of_first_period_bars() -> None:
    ema = ExponentialMovingAverage(period=3)
    series = ema.compute(candle_df(["10", "20", "30"]))
    assert series.iloc[2] == pytest.approx(20.0)


def test_subsequent_bar_applies_alpha_smoothing() -> None:
    """alpha = 2/(period+1) = 2/4 = 0.5 for period=3.
    seed at bar 2 = 20, next price = 40
    expected = 0.5 * 40 + 0.5 * 20 = 30"""
    ema = ExponentialMovingAverage(period=3)
    series = ema.compute(candle_df(["10", "20", "30", "40"]))
    assert series.iloc[3] == pytest.approx(30.0)


def test_constant_input_converges_to_that_value() -> None:
    ema = ExponentialMovingAverage(period=5)
    series = ema.compute(candle_df(["42.5"] * 10))
    assert series.iloc[-1] == pytest.approx(42.5)


def test_period_zero_raises() -> None:
    with pytest.raises(ValueError, match="period must be > 0"):
        ExponentialMovingAverage(period=0)
