"""SimpleMovingAverage: pd.Series.rolling(period).mean()."""

from __future__ import annotations

import pandas as pd

from cryptozavr.application.backtest.indicators.price import extract_price_series
from cryptozavr.application.strategy.enums import PriceSource


class SimpleMovingAverage:
    def __init__(self, period: int, source: PriceSource = PriceSource.CLOSE) -> None:
        if period <= 0:
            raise ValueError(f"SMA period must be > 0 (got {period!r})")
        self._period = period
        self._source = source

    @property
    def period(self) -> int:
        return self._period

    def compute(self, df: pd.DataFrame) -> pd.Series:
        source_series = extract_price_series(df, self._source)
        return source_series.rolling(window=self._period, min_periods=self._period).mean()
