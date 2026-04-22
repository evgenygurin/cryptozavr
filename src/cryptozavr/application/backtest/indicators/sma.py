"""SimpleMovingAverage: rolling-sum O(1) per update."""

from __future__ import annotations

from collections import deque
from decimal import Decimal

from cryptozavr.application.backtest.indicators.price import extract_price
from cryptozavr.application.strategy.enums import PriceSource
from cryptozavr.domain.market_data import OHLCVCandle


class SimpleMovingAverage:
    def __init__(self, period: int, source: PriceSource = PriceSource.CLOSE) -> None:
        if period <= 0:
            raise ValueError(f"SMA period must be > 0 (got {period!r})")
        self._period = period
        self._source = source
        self._window: deque[Decimal] = deque(maxlen=period)
        self._running_sum: Decimal = Decimal("0")

    @property
    def period(self) -> int:
        return self._period

    @property
    def is_warm(self) -> bool:
        return len(self._window) == self._period

    def update(self, candle: OHLCVCandle) -> Decimal | None:
        value = extract_price(candle, self._source)
        if len(self._window) == self._period:
            # Ejecting the oldest — decrement running sum before overwrite.
            self._running_sum -= self._window[0]
        self._window.append(value)
        self._running_sum += value
        if len(self._window) < self._period:
            return None
        return self._running_sum / Decimal(self._period)
