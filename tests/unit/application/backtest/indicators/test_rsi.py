"""RelativeStrengthIndex: Wilder smoothing with RSI=100 on no-loss."""

from __future__ import annotations

import math

import pytest

from cryptozavr.application.backtest.indicators.rsi import RelativeStrengthIndex
from tests.unit.application.backtest.fixtures import candle_df


def test_first_period_bars_nan() -> None:
    rsi = RelativeStrengthIndex(period=3)
    series = rsi.compute(candle_df(["100", "101", "102"]))
    assert math.isnan(series.iloc[0])
    assert math.isnan(series.iloc[1])
    assert math.isnan(series.iloc[2])


def test_all_gains_gives_rsi_100() -> None:
    """All deltas positive ⇒ avg_loss = 0 ⇒ RSI = 100 convention."""
    rsi = RelativeStrengthIndex(period=3)
    series = rsi.compute(candle_df(["100", "101", "102", "103"]))
    assert series.iloc[3] == pytest.approx(100.0)


def test_all_losses_gives_rsi_zero() -> None:
    rsi = RelativeStrengthIndex(period=3)
    series = rsi.compute(candle_df(["100", "99", "98", "97"]))
    assert series.iloc[3] == pytest.approx(0.0)


def test_balanced_gives_rsi_50() -> None:
    """Symmetric +10 / -10 ⇒ avg_gain == avg_loss ⇒ RS = 1 ⇒ RSI = 50."""
    rsi = RelativeStrengthIndex(period=2)
    series = rsi.compute(candle_df(["100", "110", "100"]))
    assert series.iloc[2] == pytest.approx(50.0)


def test_hand_computed_mixed_series() -> None:
    """period=2; closes [100, 110, 105, 108].
    Deltas: +10, -5, +3. Seed (first 2): avg_gain=5, avg_loss=2.5.
    Next: avg_gain = (5*1 + 3)/2 = 4; avg_loss = (2.5*1 + 0)/2 = 1.25
    RS = 3.2 ⇒ RSI = 100 - 100/4.2 ≈ 76.190476..."""
    rsi = RelativeStrengthIndex(period=2)
    series = rsi.compute(candle_df(["100", "110", "105", "108"]))
    assert series.iloc[3] == pytest.approx(100.0 - 100.0 / 4.2, rel=1e-10)


def test_period_zero_raises() -> None:
    with pytest.raises(ValueError, match="period must be > 0"):
        RelativeStrengthIndex(period=0)
