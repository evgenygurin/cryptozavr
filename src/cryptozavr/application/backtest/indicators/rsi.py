"""RelativeStrengthIndex (Wilder smoothing).

Warm after `period + 1` bars — needs `period` deltas.
Edge: avg_loss == 0 ⇒ RSI = 100 (max-bullish convention).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from cryptozavr.application.backtest.indicators.price import extract_price_series
from cryptozavr.application.strategy.enums import PriceSource


class RelativeStrengthIndex:
    def __init__(self, period: int = 14, source: PriceSource = PriceSource.CLOSE) -> None:
        if period <= 0:
            raise ValueError(f"RSI period must be > 0 (got {period!r})")
        self._period = period
        self._source = source

    @property
    def period(self) -> int:
        return self._period

    def compute(self, df: pd.DataFrame) -> pd.Series:
        prices = extract_price_series(df, self._source).to_numpy(dtype=np.float64)
        n = len(prices)
        out = np.full(n, np.nan, dtype=np.float64)
        if n < self._period + 1:
            return pd.Series(out, index=df.index)
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        # Seed: SMA of first `period` gains / losses.
        avg_gain = gains[: self._period].mean()
        avg_loss = losses[: self._period].mean()
        out[self._period] = _rsi_from_avgs(avg_gain, avg_loss)
        # Wilder smoothing for subsequent bars.
        for i in range(self._period + 1, n):
            gain_i = gains[i - 1]
            loss_i = losses[i - 1]
            avg_gain = (avg_gain * (self._period - 1) + gain_i) / self._period
            avg_loss = (avg_loss * (self._period - 1) + loss_i) / self._period
            out[i] = _rsi_from_avgs(avg_gain, avg_loss)
        return pd.Series(out, index=df.index)


def _rsi_from_avgs(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)
