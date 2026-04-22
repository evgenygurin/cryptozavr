"""RelativeStrengthIndex: Wilder smoothing on gain/loss."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.application.backtest.indicators.rsi import RelativeStrengthIndex
from tests.unit.application.backtest.indicators.fixtures import candle


def test_first_bar_returns_none_no_delta_yet() -> None:
    rsi = RelativeStrengthIndex(period=3)
    assert rsi.update(candle(0, close="100")) is None


def test_warm_up_needs_period_plus_one_bars() -> None:
    rsi = RelativeStrengthIndex(period=3)
    # Period=3 ⇒ need bar 0 to seed prev_price, then 3 deltas.
    values = [100, 101, 102, 103]
    results = [rsi.update(candle(i, close=str(v))) for i, v in enumerate(values)]
    assert results[:3] == [None, None, None]
    # All deltas positive ⇒ avg_loss = 0 ⇒ RSI = 100
    assert results[3] == Decimal("100")


def test_all_losses_gives_rsi_zero() -> None:
    """All deltas negative ⇒ avg_gain = 0 ⇒ RSI = 100 - 100/(1+0) = 0."""
    rsi = RelativeStrengthIndex(period=3)
    values = [100, 99, 98, 97]
    for i, v in enumerate(values):
        result = rsi.update(candle(i, close=str(v)))
    assert result == Decimal("0")


def test_balanced_gains_and_losses_gives_rsi_50() -> None:
    """Symmetric gains/losses ⇒ avg_gain = avg_loss ⇒ RS = 1 ⇒ RSI = 50."""
    rsi = RelativeStrengthIndex(period=2)
    # Deltas: +10, -10 → avg_gain = 5, avg_loss = 5
    values = [100, 110, 100]
    result = None
    for i, v in enumerate(values):
        result = rsi.update(candle(i, close=str(v)))
    assert result == Decimal("50")


def test_hand_computed_mixed_series() -> None:
    """Period=2; closes [100, 110, 105, 108].
    Deltas: +10, -5, +3. After seed (first 2 deltas):
      avg_gain = 10/2 = 5
      avg_loss = 5/2 = 2.5
    Then delta +3:
      avg_gain = (5*1 + 3)/2 = 4
      avg_loss = (2.5*1 + 0)/2 = 1.25
      RS = 4/1.25 = 3.2
      RSI = 100 - 100/(1+3.2) = 100 - 100/4.2 ≈ 76.190476...
    """
    rsi = RelativeStrengthIndex(period=2)
    for i, v in enumerate((100, 110, 105)):
        rsi.update(candle(i, close=str(v)))
    result = rsi.update(candle(3, close="108"))
    expected = Decimal("100") - Decimal("100") / (Decimal("1") + Decimal("3.2"))
    assert result is not None
    assert abs(result - expected) < Decimal("1e-20")


def test_rsi_stays_in_zero_hundred() -> None:
    """Any (bounded, non-equal) series produces RSI ∈ [0, 100]."""
    rsi = RelativeStrengthIndex(period=5)
    values = [100, 105, 102, 108, 103, 110, 104, 112]
    for i, v in enumerate(values):
        r = rsi.update(candle(i, close=str(v)))
        if r is not None:
            assert Decimal("0") <= r <= Decimal("100")


def test_period_zero_raises() -> None:
    with pytest.raises(ValueError, match="period must be > 0"):
        RelativeStrengthIndex(period=0)
