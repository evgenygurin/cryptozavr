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
    """Pin the EMA recurrence `alpha*price + (1-alpha)*prev` with asymmetric alpha.

    A symmetric alpha (0.5) would make `alpha*price + (1-alpha)*prev` and the
    swapped `alpha*prev + (1-alpha)*price` produce the same value, so the
    formula isn't actually pinned. We use period=4 → alpha = 2/(4+1) = 0.4
    to break the symmetry.

    Series: ["100", "100", "100", "100", "150"]
    - Seed at bar 3 (period-1 = 3) = mean of first 4 = 100
    - Bar 4 (correct): 0.4 * 150 + 0.6 * 100 = 60 + 60 = 120
    - Bar 4 (swapped): 0.6 * 150 + 0.4 * 100 = 90 + 40 = 130

    The 120 vs 130 gap catches any mistakenly swapped recurrence.
    """
    ema = ExponentialMovingAverage(period=4)
    series = ema.compute(candle_df(["100", "100", "100", "100", "150"]))
    assert series.iloc[3] == pytest.approx(100.0)
    assert series.iloc[4] == pytest.approx(120.0)


def test_constant_input_converges_to_that_value() -> None:
    ema = ExponentialMovingAverage(period=5)
    series = ema.compute(candle_df(["42.5"] * 10))
    assert series.iloc[-1] == pytest.approx(42.5)


def test_period_zero_raises() -> None:
    with pytest.raises(ValueError, match="period must be > 0"):
        ExponentialMovingAverage(period=0)


def test_series_shorter_than_period_is_all_nan() -> None:
    """When fewer bars than period are provided, every output is NaN."""
    ema = ExponentialMovingAverage(period=5)
    series = ema.compute(candle_df(["10", "20", "30"]))
    assert all(math.isnan(v) for v in series)
    assert len(series) == 3
