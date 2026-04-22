"""ExponentialMovingAverage.

Uses SMA of the first `period` bars as the seed, then applies
`EMA_t = alpha * price + (1 - alpha) * EMA_{t-1}` where
`alpha = 2 / (period + 1)`. Matches TA-Lib / TradingView conventions.
"""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.backtest.indicators.price import extract_price
from cryptozavr.application.strategy.enums import PriceSource
from cryptozavr.domain.market_data import OHLCVCandle


class ExponentialMovingAverage:
    def __init__(self, period: int, source: PriceSource = PriceSource.CLOSE) -> None:
        if period <= 0:
            raise ValueError(f"EMA period must be > 0 (got {period!r})")
        self._period = period
        self._source = source
        self._alpha = Decimal(2) / Decimal(period + 1)
        self._one_minus_alpha = Decimal(1) - self._alpha
        self._seed_sum: Decimal = Decimal("0")
        self._seed_count = 0
        self._value: Decimal | None = None

    @property
    def period(self) -> int:
        return self._period

    @property
    def is_warm(self) -> bool:
        return self._value is not None

    def update(self, candle: OHLCVCandle) -> Decimal | None:
        price = extract_price(candle, self._source)
        if self._value is None:
            # Still seeding with SMA of the first `period` bars.
            self._seed_sum += price
            self._seed_count += 1
            if self._seed_count < self._period:
                return None
            self._value = self._seed_sum / Decimal(self._period)
            return self._value
        # Warm path: classic EMA recurrence.
        self._value = self._alpha * price + self._one_minus_alpha * self._value
        return self._value
