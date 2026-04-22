"""AverageTrueRange (Wilder smoothing).

TR_t = max(high_t - low_t, |high_t - close_{t-1}|, |low_t - close_{t-1}|)
ATR_0 (first warm bar) = mean of the first `period` TRs
ATR_t = (ATR_{t-1} * (period - 1) + TR_t) / period

Not parameterised by PriceSource — true range is an OHLC-specific concept.
Warm after period + 1 bars (need one prior close to compute TR for bar 1).
"""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.domain.market_data import OHLCVCandle


class AverageTrueRange:
    def __init__(self, period: int = 14) -> None:
        if period <= 0:
            raise ValueError(f"ATR period must be > 0 (got {period!r})")
        self._period = period
        self._prev_close: Decimal | None = None
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
        if self._prev_close is None:
            # First bar — can't compute TR yet (no previous close).
            self._prev_close = candle.close
            return None
        tr = max(
            candle.high - candle.low,
            abs(candle.high - self._prev_close),
            abs(candle.low - self._prev_close),
        )
        self._prev_close = candle.close
        if self._value is None:
            # Still seeding.
            self._seed_sum += tr
            self._seed_count += 1
            if self._seed_count < self._period:
                return None
            self._value = self._seed_sum / Decimal(self._period)
            return self._value
        # Wilder smoothing.
        self._value = (self._value * Decimal(self._period - 1) + tr) / Decimal(self._period)
        return self._value
