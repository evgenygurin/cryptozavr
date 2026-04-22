"""MACD (line only for 2B.1).

Two EMAs — fast (default 12) and slow (default 26). `update()` returns
the MACD line = fast_ema - slow_ema once both are warm. Signal and
histogram are deferred until a 2A+1 DSL extension needs them.

Warms after `slow` bars (slow EMA dominates the warm-up budget).
"""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.backtest.indicators.ema import ExponentialMovingAverage
from cryptozavr.application.strategy.enums import PriceSource
from cryptozavr.domain.market_data import OHLCVCandle


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
            raise ValueError(
                f"MACD fast must be < slow (got fast={fast}, slow={slow})",
            )
        self._fast_ema = ExponentialMovingAverage(period=fast, source=source)
        self._slow_ema = ExponentialMovingAverage(period=slow, source=source)
        self._slow = slow

    @property
    def period(self) -> int:
        return self._slow

    @property
    def is_warm(self) -> bool:
        return self._slow_ema.is_warm

    def update(self, candle: OHLCVCandle) -> Decimal | None:
        fast = self._fast_ema.update(candle)
        slow = self._slow_ema.update(candle)
        if slow is None:
            return None
        # Fast warms before slow (shorter period), so slow-warm implies
        # fast-warm. `fast is None` can't happen once we've past the slow
        # warm-up, but assert defensively.
        assert fast is not None
        return fast - slow
