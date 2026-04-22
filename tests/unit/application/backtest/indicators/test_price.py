"""extract_price_series: DataFrame + PriceSource -> pd.Series[float]."""

from __future__ import annotations

import pandas as pd

from cryptozavr.application.backtest.indicators.price import extract_price_series
from cryptozavr.application.strategy.enums import PriceSource
from tests.unit.application.backtest.fixtures import candle_df


def test_open_source() -> None:
    df = candle_df(["100", "105", "110"])
    series = extract_price_series(df, PriceSource.OPEN)
    assert list(series) == [100.0, 105.0, 110.0]


def test_high_source() -> None:
    df = candle_df(["100", "105"], high_bump="2")
    series = extract_price_series(df, PriceSource.HIGH)
    assert list(series) == [102.0, 107.0]


def test_low_source() -> None:
    df = candle_df(["100", "105"], low_bump="3")
    series = extract_price_series(df, PriceSource.LOW)
    assert list(series) == [97.0, 102.0]


def test_close_source() -> None:
    df = candle_df(["100", "105", "110"])
    series = extract_price_series(df, PriceSource.CLOSE)
    assert list(series) == [100.0, 105.0, 110.0]


def test_hlc3_source() -> None:
    """HLC3 = (high + low + close) / 3 element-wise."""
    df = candle_df(["99"], high_bump="3", low_bump="0")
    # high=102, low=99, close=99 → HLC3 = 100
    series = extract_price_series(df, PriceSource.HLC3)
    assert series.iloc[0] == pd.Series([100.0]).iloc[0]
