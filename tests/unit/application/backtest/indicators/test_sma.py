"""SimpleMovingAverage vectorized: rolling mean over `period` bars."""

from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cryptozavr.application.backtest.indicators.sma import SimpleMovingAverage
from cryptozavr.application.strategy.enums import PriceSource
from tests.unit.application.backtest.fixtures import candle_df


def test_warm_up_returns_nan_until_period_bars() -> None:
    sma = SimpleMovingAverage(period=3)
    series = sma.compute(candle_df(["10", "20"]))
    assert math.isnan(series.iloc[0])
    assert math.isnan(series.iloc[1])


def test_first_warm_value_matches_mean() -> None:
    sma = SimpleMovingAverage(period=3)
    series = sma.compute(candle_df(["10", "20", "30"]))
    assert math.isnan(series.iloc[1])
    assert series.iloc[2] == pytest.approx(20.0)


def test_window_rolls_on_subsequent_bars() -> None:
    sma = SimpleMovingAverage(period=3)
    series = sma.compute(candle_df(["10", "20", "30", "40"]))
    assert series.iloc[3] == pytest.approx(30.0)


def test_period_one_emits_latest_every_bar() -> None:
    sma = SimpleMovingAverage(period=1)
    series = sma.compute(candle_df(["50", "55"]))
    assert series.iloc[0] == 50.0
    assert series.iloc[1] == 55.0


def test_uses_source_field() -> None:
    sma = SimpleMovingAverage(period=2, source=PriceSource.HIGH)
    df = candle_df(["100", "200"], high_bump="0")  # high == close
    series = sma.compute(df)
    assert series.iloc[1] == pytest.approx(150.0)


def test_period_zero_raises() -> None:
    with pytest.raises(ValueError, match="period must be > 0"):
        SimpleMovingAverage(period=0)


def test_period_negative_raises() -> None:
    with pytest.raises(ValueError, match="period must be > 0"):
        SimpleMovingAverage(period=-1)


@given(
    st.lists(
        st.floats(
            min_value=1.0,
            max_value=1_000_000.0,
            allow_nan=False,
            allow_infinity=False,
        ),
        min_size=5,
        max_size=30,
    )
)
def test_property_sma_matches_naive_sliding_mean(values: list[float]) -> None:
    period = 3
    sma = SimpleMovingAverage(period=period)
    df = candle_df([str(v) for v in values])
    series = sma.compute(df)
    for i in range(period - 1):
        assert math.isnan(series.iloc[i])
    for i in range(period - 1, len(values)):
        expected = sum(values[i - period + 1 : i + 1]) / period
        assert series.iloc[i] == pytest.approx(expected, rel=1e-9)
