"""MACD line (fast EMA - slow EMA). Signal + histogram deferred until
a 2A+1 DSL extension exposes them separately."""

from __future__ import annotations

import pandas as pd

from cryptozavr.application.backtest.indicators.ema import ExponentialMovingAverage
from cryptozavr.application.strategy.enums import PriceSource


class MACD:
    def __init__(
        self,
        *,
        fast: int = 12,
        slow: int = 26,
        source: PriceSource = PriceSource.CLOSE,
    ) -> None:
        if fast <= 0 or slow <= 0:
            raise ValueError(f"MACD fast/slow must be > 0 (got fast={fast}, slow={slow})")
        if fast >= slow:
            raise ValueError(f"MACD fast must be < slow (got fast={fast}, slow={slow})")
        self._fast = ExponentialMovingAverage(period=fast, source=source)
        self._slow = ExponentialMovingAverage(period=slow, source=source)
        self._slow_period = slow

    @property
    def period(self) -> int:
        return self._slow_period

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return self._fast.compute(df) - self._slow.compute(df)
