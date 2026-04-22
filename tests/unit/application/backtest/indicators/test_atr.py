"""AverageTrueRange: Wilder-smoothed TR = max(H-L, |H-prevC|, |L-prevC|)."""

from __future__ import annotations

import math

import pytest

from cryptozavr.application.backtest.indicators.atr import AverageTrueRange
from tests.unit.application.backtest.fixtures import candle_df


def test_first_period_bars_nan() -> None:
    atr = AverageTrueRange(period=3)
    # Period=3 needs prev_close bar + 3 TR bars = 4 bars before warm.
    series = atr.compute(candle_df(["100", "101", "102"]))
    assert math.isnan(series.iloc[0])
    assert math.isnan(series.iloc[2])


def test_seeded_mean_of_first_period_trs() -> None:
    """closes = [100, 103, 105, 107], bumps high=+1/low=-1 by fixture default.
    Bar 0: h=101, l=99, c=100 (seeds prev_close)
    Bar 1: h=104, l=102, c=103, prev_close=100 → TR=max(2, |104-100|, |102-100|)=4
    Bar 2: h=106, l=104, c=105, prev_close=103 → TR=max(2, |106-103|, |104-103|)=3
    Bar 3: h=108, l=106, c=107, prev_close=105 → TR=max(2, |108-105|, |106-105|)=3
    Seed (period=3): (4+3+3)/3 = 10/3 ≈ 3.333"""
    atr = AverageTrueRange(period=3)
    series = atr.compute(candle_df(["100", "103", "105", "107"]))
    assert series.iloc[3] == pytest.approx(10.0 / 3.0, rel=1e-12)


def test_wilder_smoothing_after_seed() -> None:
    """Continue: bar 4 c=113 (fixture h=114, l=112), prev_close=107.
    TR=max(h-l=2, |h-prevC|=7, |l-prevC|=5)=7
    ATR_4 = (ATR_3 * (period-1) + TR_4) / period = (10/3 * 2 + 7) / 3 = 41/9"""
    atr = AverageTrueRange(period=3)
    closes = ["100", "103", "105", "107", "113"]
    series = atr.compute(candle_df(closes))
    assert series.iloc[4] == pytest.approx(41.0 / 9.0, rel=1e-12)


def test_period_zero_raises() -> None:
    with pytest.raises(ValueError, match="period must be > 0"):
        AverageTrueRange(period=0)


def test_period_one_valid() -> None:
    atr = AverageTrueRange(period=1)
    series = atr.compute(candle_df(["100", "103"]))
    # Bar 1: h=104, l=102, prev_close=100. TR=max(2, 4, 2)=4. Seed mean of 1 TR = 4.
    assert series.iloc[1] == pytest.approx(4.0)
