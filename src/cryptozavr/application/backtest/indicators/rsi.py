"""RelativeStrengthIndex (Wilder smoothing).

gain_t = max(price_t - price_{t-1}, 0)
loss_t = max(price_{t-1} - price_t, 0)
avg_gain_0 = mean(gain_{1..period})   (SMA seed)
avg_loss_0 = mean(loss_{1..period})
# Wilder smoothing after warm-up:
avg_gain_t = (avg_gain_{t-1} * (period-1) + gain_t) / period
avg_loss_t = (avg_loss_{t-1} * (period-1) + loss_t) / period
RSI_t = 100 - 100 / (1 + avg_gain_t/avg_loss_t)

Edge: avg_loss == 0 ⇒ RSI = 100 by convention (max bullish).
Warm after period + 1 bars (need period deltas).
"""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.backtest.indicators.price import extract_price
from cryptozavr.application.strategy.enums import PriceSource
from cryptozavr.domain.market_data import OHLCVCandle

_HUNDRED = Decimal("100")
_ONE = Decimal("1")
_ZERO = Decimal("0")


class RelativeStrengthIndex:
    def __init__(self, period: int = 14, source: PriceSource = PriceSource.CLOSE) -> None:
        if period <= 0:
            raise ValueError(f"RSI period must be > 0 (got {period!r})")
        self._period = period
        self._source = source
        self._prev_price: Decimal | None = None
        self._seed_gain = _ZERO
        self._seed_loss = _ZERO
        self._seed_count = 0
        self._avg_gain: Decimal | None = None
        self._avg_loss: Decimal | None = None

    @property
    def period(self) -> int:
        return self._period

    @property
    def is_warm(self) -> bool:
        return self._avg_gain is not None

    def update(self, candle: OHLCVCandle) -> Decimal | None:
        price = extract_price(candle, self._source)
        if self._prev_price is None:
            # First bar — no delta yet.
            self._prev_price = price
            return None
        delta = price - self._prev_price
        self._prev_price = price
        gain = delta if delta > _ZERO else _ZERO
        loss = -delta if delta < _ZERO else _ZERO
        if self._avg_gain is None:
            # Still seeding.
            self._seed_gain += gain
            self._seed_loss += loss
            self._seed_count += 1
            if self._seed_count < self._period:
                return None
            period_dec = Decimal(self._period)
            self._avg_gain = self._seed_gain / period_dec
            self._avg_loss = self._seed_loss / period_dec
        else:
            assert self._avg_loss is not None  # tied to _avg_gain
            n_minus_one = Decimal(self._period - 1)
            period_dec = Decimal(self._period)
            self._avg_gain = (self._avg_gain * n_minus_one + gain) / period_dec
            self._avg_loss = (self._avg_loss * n_minus_one + loss) / period_dec
        if self._avg_loss == _ZERO:
            # Max-bullish convention.
            return _HUNDRED
        rs = self._avg_gain / self._avg_loss
        return _HUNDRED - _HUNDRED / (_ONE + rs)
