"""IndicatorCache: intern refs, snapshot current->previous, expose both."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.application.backtest.evaluator.indicator_cache import IndicatorCache
from cryptozavr.application.strategy.enums import IndicatorKind
from tests.unit.application.backtest.evaluator.fixtures import ref
from tests.unit.application.backtest.indicators.fixtures import candle


def test_same_ref_registered_twice_is_interned() -> None:
    cache = IndicatorCache()
    r = ref(IndicatorKind.SMA, 5)
    cache.register(r)
    first_reg_size = len(cache._indicators)
    cache.register(r)
    assert len(cache._indicators) == first_reg_size


def test_current_value_raises_for_unregistered_ref() -> None:
    cache = IndicatorCache()
    with pytest.raises(KeyError):
        cache.current_value(ref(IndicatorKind.SMA, 5))


def test_current_and_previous_none_before_any_tick() -> None:
    cache = IndicatorCache()
    r = ref(IndicatorKind.SMA, 3)
    cache.register(r)
    assert cache.current_value(r) is None
    assert cache.previous_value(r) is None
    assert cache.all_warm() is False


def test_tick_advances_sma() -> None:
    cache = IndicatorCache()
    r = ref(IndicatorKind.SMA, 2)
    cache.register(r)
    cache.tick(candle(0, close="10"))  # warming
    assert cache.current_value(r) is None
    cache.tick(candle(1, close="20"))  # warm; SMA=15
    assert cache.current_value(r) == Decimal("15")
    assert cache.previous_value(r) is None  # prior bar was still warming


def test_previous_snaps_after_each_tick() -> None:
    cache = IndicatorCache()
    r = ref(IndicatorKind.SMA, 1)  # period=1: warm every bar
    cache.register(r)
    cache.tick(candle(0, close="10"))
    cache.tick(candle(1, close="20"))
    assert cache.current_value(r) == Decimal("20")
    assert cache.previous_value(r) == Decimal("10")


def test_all_warm_transitions_at_slowest_indicator() -> None:
    cache = IndicatorCache()
    fast = ref(IndicatorKind.SMA, 1)
    slow = ref(IndicatorKind.SMA, 3)
    cache.register(fast)
    cache.register(slow)
    cache.tick(candle(0, close="10"))
    assert cache.all_warm() is False  # slow not ready
    cache.tick(candle(1, close="20"))
    assert cache.all_warm() is False
    cache.tick(candle(2, close="30"))
    assert cache.all_warm() is True


def test_two_different_sma_periods_interned_separately() -> None:
    cache = IndicatorCache()
    a = ref(IndicatorKind.SMA, 3)
    b = ref(IndicatorKind.SMA, 5)
    cache.register(a)
    cache.register(b)
    assert cache._indicators[a] is not cache._indicators[b]
