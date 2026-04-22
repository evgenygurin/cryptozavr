"""AverageTrueRange: Wilder smoothing over true range."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.application.backtest.indicators.atr import AverageTrueRange
from tests.unit.application.backtest.indicators.fixtures import candle


def test_first_bar_returns_none_no_prior_close() -> None:
    atr = AverageTrueRange(period=3)
    assert atr.update(candle(0, high="110", low="90", close="100")) is None


def test_warm_up_needs_period_plus_one_bars() -> None:
    """Period=3 ⇒ needs bar 0 (seed prev_close) + bars 1..3 (three TRs)."""
    atr = AverageTrueRange(period=3)
    bars = [
        candle(0, high="105", low="95", close="100"),  # prev_close seed
        candle(1, high="108", low="98", close="103"),  # TR = 10
        candle(2, high="110", low="100", close="105"),  # TR = 10 (vs. prev close 103)
        candle(3, high="112", low="102", close="107"),  # TR = 10
    ]
    results = [atr.update(b) for b in bars]
    assert results[0] is None
    assert results[1] is None
    assert results[2] is None
    # Seeded mean of three TRs ≈ 10
    assert results[3] == Decimal("10")


def test_wilder_smoothing_after_seed() -> None:
    """After seed, ATR = (ATR_prev * (period-1) + TR) / period.
    seed = 10 (see test above), next TR = 20, period=3
    expected = (10*2 + 20)/3 = 40/3
    """
    atr = AverageTrueRange(period=3)
    for b in [
        candle(0, high="105", low="95", close="100"),
        candle(1, high="108", low="98", close="103"),
        candle(2, high="110", low="100", close="105"),
        candle(3, high="112", low="102", close="107"),
    ]:
        atr.update(b)
    # Bar 4: high=130, low=110, close=120, prev_close=107
    # TR = max(130-110, |130-107|, |110-107|) = max(20, 23, 3) = 23
    # expected = (10*2 + 23)/3 = 43/3 ≈ 14.333...
    result = atr.update(candle(4, high="130", low="110", close="120"))
    expected = Decimal("43") / Decimal("3")
    assert result is not None
    assert abs(result - expected) < Decimal("1e-20")


def test_true_range_uses_prev_close_gap() -> None:
    """When prev_close is outside today's range, TR uses the gap, not the
    intrabar range."""
    atr = AverageTrueRange(period=2)
    # Seed + gap-up bar
    atr.update(candle(0, high="100", low="99", close="100"))
    # Bar 1: prev_close=100, intrabar range 105-104=1, but gap 105-100=5
    # TR = max(1, |105-100|, |104-100|) = 5
    atr.update(candle(1, high="105", low="104", close="104.5"))
    # Bar 2: prev_close=104.5, intrabar 107-106=1, gap 107-104.5=2.5
    # TR = max(1, 2.5, |106-104.5|) = 2.5
    result = atr.update(candle(2, high="107", low="106", close="106.5"))
    # Seeded mean of (5, 2.5) = 3.75
    assert result == Decimal("3.75")


def test_period_zero_raises() -> None:
    with pytest.raises(ValueError, match="period must be > 0"):
        AverageTrueRange(period=0)
