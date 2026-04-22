"""AverageTrueRange (Wilder smoothing).

TR_t = max(high_t - low_t, |high_t - close_{t-1}|, |low_t - close_{t-1}|)
Seed: mean of first `period` TRs. Warm after period+1 bars (bar 0 seeds
prev_close without emitting a TR). Not parameterised by PriceSource —
TR is an OHLC-specific concept.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class AverageTrueRange:
    def __init__(self, period: int = 14) -> None:
        if period <= 0:
            raise ValueError(f"ATR period must be > 0 (got {period!r})")
        self._period = period

    @property
    def period(self) -> int:
        return self._period

    def compute(self, df: pd.DataFrame) -> pd.Series:
        highs = df["high"].to_numpy(dtype=np.float64)
        lows = df["low"].to_numpy(dtype=np.float64)
        closes = df["close"].to_numpy(dtype=np.float64)
        n = len(closes)
        out = np.full(n, np.nan, dtype=np.float64)
        if n < self._period + 1:
            return pd.Series(out, index=df.index)
        prev_close = closes[:-1]
        tr_from_bar1 = np.maximum.reduce(
            [
                highs[1:] - lows[1:],
                np.abs(highs[1:] - prev_close),
                np.abs(lows[1:] - prev_close),
            ]
        )
        # Seed: mean of first `period` TRs (tr_from_bar1 starts at bar index 1).
        seed = tr_from_bar1[: self._period].mean()
        out[self._period] = seed
        prev_atr = seed
        for i in range(self._period + 1, n):
            tr_i = tr_from_bar1[i - 1]
            prev_atr = (prev_atr * (self._period - 1) + tr_i) / self._period
            out[i] = prev_atr
        return pd.Series(out, index=df.index)
