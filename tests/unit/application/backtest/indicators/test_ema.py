"""ExponentialMovingAverage: SMA-seeded + alpha smoothing."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.application.backtest.indicators.ema import ExponentialMovingAverage
from cryptozavr.application.strategy.enums import PriceSource
from tests.unit.application.backtest.indicators.fixtures import candle, closes


def test_warm_up_returns_none_until_period_bars() -> None:
    ema = ExponentialMovingAverage(period=3)
    bars = closes(("10", "20"))
    for bar in bars:
        assert ema.update(bar) is None
    assert ema.is_warm is False


def test_first_warm_value_is_sma_of_first_period_bars() -> None:
    ema = ExponentialMovingAverage(period=3)
    bars = closes(("10", "20", "30"))
    result = None
    for bar in bars:
        result = ema.update(bar)
    assert result == Decimal("20")
    assert ema.is_warm is True


def test_subsequent_value_applies_alpha_smoothing() -> None:
    """After seeding, EMA = alpha*price + (1-alpha)*prev_ema.
    alpha = 2 / (period+1) = 2/4 = 0.5 for period=3.
    seed = (10+20+30)/3 = 20, next price = 40
    expected = 0.5*40 + 0.5*20 = 30
    """
    ema = ExponentialMovingAverage(period=3)
    for bar in closes(("10", "20", "30")):
        ema.update(bar)
    result = ema.update(candle(3, close="40"))
    assert result == Decimal("30")


def test_constant_input_converges_to_that_value() -> None:
    """EMA of a flat series is that value exactly (alpha smoothing doesn't
    move a stationary input)."""
    ema = ExponentialMovingAverage(period=5)
    result: Decimal | None = None
    for i in range(10):
        result = ema.update(candle(i, close="42.5"))
    assert result == Decimal("42.5")


def test_uses_source_field() -> None:
    ema = ExponentialMovingAverage(period=2, source=PriceSource.HIGH)
    ema.update(candle(0, high="100"))
    result = ema.update(candle(1, high="200"))
    # period=2, alpha=2/3. After period bars: seed = (100+200)/2 = 150.
    assert result == Decimal("150")


def test_period_zero_raises() -> None:
    with pytest.raises(ValueError, match="period must be > 0"):
        ExponentialMovingAverage(period=0)
