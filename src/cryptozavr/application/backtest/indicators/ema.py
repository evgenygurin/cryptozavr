"""ExponentialMovingAverage: SMA seed for first `period` bars, then
alpha * price + (1-alpha) * prev recurrence.

Implementation is a manual loop because pandas `.ewm(adjust=False)`
emits values from bar 0 without an SMA warm-up (produces a different
curve from the TA-Lib / TradingView convention). We keep the loop but
operate on numpy arrays — faster than per-row pandas access.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from cryptozavr.application.backtest.indicators.price import extract_price_series
from cryptozavr.application.strategy.enums import PriceSource


class ExponentialMovingAverage:
    def __init__(self, period: int, source: PriceSource = PriceSource.CLOSE) -> None:
        if period <= 0:
            raise ValueError(f"EMA period must be > 0 (got {period!r})")
        self._period = period
        self._source = source

    @property
    def period(self) -> int:
        return self._period

    def compute(self, df: pd.DataFrame) -> pd.Series:
        prices = extract_price_series(df, self._source).to_numpy(dtype=np.float64)
        n = len(prices)
        out = np.full(n, np.nan, dtype=np.float64)
        if n < self._period:
            return pd.Series(out, index=df.index)
        alpha = 2.0 / (self._period + 1)
        # Seed: SMA of first `period` bars.
        seed = prices[: self._period].mean()
        out[self._period - 1] = seed
        prev = seed
        for i in range(self._period, n):
            prev = alpha * prices[i] + (1.0 - alpha) * prev
            out[i] = prev
        return pd.Series(out, index=df.index)
