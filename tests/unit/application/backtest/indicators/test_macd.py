"""MACD line = fast EMA - slow EMA."""

from __future__ import annotations

import math

import pytest

from cryptozavr.application.backtest.indicators.ema import ExponentialMovingAverage
from cryptozavr.application.backtest.indicators.macd import MACD
from tests.unit.application.backtest.fixtures import candle_df


def test_warm_up_nan_until_slow_period() -> None:
    macd = MACD(fast=2, slow=4)
    series = macd.compute(candle_df(["100", "101", "103"]))
    assert math.isnan(series.iloc[0])
    assert math.isnan(series.iloc[2])


def test_line_equals_fast_ema_minus_slow_ema() -> None:
    macd = MACD(fast=2, slow=4)
    fast_ref = ExponentialMovingAverage(period=2)
    slow_ref = ExponentialMovingAverage(period=4)
    closes = ["100", "101", "103", "102", "105", "104", "107"]
    df = candle_df(closes)
    macd_series = macd.compute(df)
    fast_series = fast_ref.compute(df)
    slow_series = slow_ref.compute(df)
    for i in range(len(closes)):
        if math.isnan(macd_series.iloc[i]):
            assert math.isnan(slow_series.iloc[i])
        else:
            assert macd_series.iloc[i] == pytest.approx(
                fast_series.iloc[i] - slow_series.iloc[i], rel=1e-12
            )


def test_constant_input_gives_zero() -> None:
    macd = MACD(fast=2, slow=4)
    series = macd.compute(candle_df(["100"] * 20))
    assert series.iloc[-1] == pytest.approx(0.0, abs=1e-12)


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
