"""evaluate_condition: all 6 ComparatorOps, Decimal RHS, None propagation."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.backtest.evaluator.condition import evaluate_condition
from cryptozavr.application.backtest.evaluator.indicator_cache import IndicatorCache
from cryptozavr.application.strategy.enums import ComparatorOp, IndicatorKind
from cryptozavr.application.strategy.strategy_spec import Condition
from tests.unit.application.backtest.evaluator.fixtures import ref
from tests.unit.application.backtest.indicators.fixtures import candle


def _cache_with(values: list[str]) -> tuple[IndicatorCache, Condition]:
    """Create a cache with a single period-1 SMA (warm every bar) fed
    the given close values. Returns cache + a reusable condition object."""
    cache = IndicatorCache()
    r = ref(IndicatorKind.SMA, 1)
    cache.register(r)
    for i, v in enumerate(values):
        cache.tick(candle(i, close=v))
    cond = Condition(lhs=r, op=ComparatorOp.GT, rhs=Decimal("50"))
    return cache, cond


def test_gt_true() -> None:
    cache, _ = _cache_with(["100"])
    cond = Condition(lhs=ref(IndicatorKind.SMA, 1), op=ComparatorOp.GT, rhs=Decimal("50"))
    assert evaluate_condition(cond, cache) is True


def test_gt_false() -> None:
    cache, _ = _cache_with(["10"])
    cond = Condition(lhs=ref(IndicatorKind.SMA, 1), op=ComparatorOp.GT, rhs=Decimal("50"))
    assert evaluate_condition(cond, cache) is False


def test_gte_equal() -> None:
    cache, _ = _cache_with(["50"])
    cond = Condition(lhs=ref(IndicatorKind.SMA, 1), op=ComparatorOp.GTE, rhs=Decimal("50"))
    assert evaluate_condition(cond, cache) is True


def test_lt_true() -> None:
    cache, _ = _cache_with(["10"])
    cond = Condition(lhs=ref(IndicatorKind.SMA, 1), op=ComparatorOp.LT, rhs=Decimal("50"))
    assert evaluate_condition(cond, cache) is True


def test_lte_equal() -> None:
    cache, _ = _cache_with(["50"])
    cond = Condition(lhs=ref(IndicatorKind.SMA, 1), op=ComparatorOp.LTE, rhs=Decimal("50"))
    assert evaluate_condition(cond, cache) is True


def test_crosses_above_true_on_crossing_bar() -> None:
    """prev lhs <= prev rhs AND curr lhs > curr rhs."""
    cache = IndicatorCache()
    r = ref(IndicatorKind.SMA, 1)
    cache.register(r)
    cache.tick(candle(0, close="40"))  # prev=40, curr=40 (no prev yet)
    cache.tick(candle(1, close="60"))  # prev=40, curr=60
    cond = Condition(lhs=r, op=ComparatorOp.CROSSES_ABOVE, rhs=Decimal("50"))
    assert evaluate_condition(cond, cache) is True


def test_crosses_above_false_when_both_above() -> None:
    cache = IndicatorCache()
    r = ref(IndicatorKind.SMA, 1)
    cache.register(r)
    cache.tick(candle(0, close="60"))
    cache.tick(candle(1, close="70"))
    cond = Condition(lhs=r, op=ComparatorOp.CROSSES_ABOVE, rhs=Decimal("50"))
    assert evaluate_condition(cond, cache) is False


def test_crosses_below_true_on_crossing_bar() -> None:
    cache = IndicatorCache()
    r = ref(IndicatorKind.SMA, 1)
    cache.register(r)
    cache.tick(candle(0, close="60"))
    cache.tick(candle(1, close="40"))
    cond = Condition(lhs=r, op=ComparatorOp.CROSSES_BELOW, rhs=Decimal("50"))
    assert evaluate_condition(cond, cache) is True


def test_crosses_ops_return_none_without_previous_value() -> None:
    cache = IndicatorCache()
    r = ref(IndicatorKind.SMA, 1)
    cache.register(r)
    cache.tick(candle(0, close="40"))  # first warm bar, no previous
    cond = Condition(lhs=r, op=ComparatorOp.CROSSES_ABOVE, rhs=Decimal("50"))
    assert evaluate_condition(cond, cache) is None


def test_none_when_indicator_warming() -> None:
    """If the indicator hasn't emitted yet, comparison is None even against
    a Decimal constant."""
    cache = IndicatorCache()
    r = ref(IndicatorKind.SMA, 3)  # needs 3 bars
    cache.register(r)
    cache.tick(candle(0, close="100"))  # still warming
    cond = Condition(lhs=r, op=ComparatorOp.GT, rhs=Decimal("50"))
    assert evaluate_condition(cond, cache) is None


def test_indicator_vs_indicator_comparison() -> None:
    cache = IndicatorCache()
    a = ref(IndicatorKind.SMA, 1)
    b = ref(IndicatorKind.EMA, 2)
    cache.register(a)
    cache.register(b)
    # Warm both
    cache.tick(candle(0, close="100"))
    cache.tick(candle(1, close="100"))
    cond = Condition(lhs=a, op=ComparatorOp.GTE, rhs=b)
    assert evaluate_condition(cond, cache) is True


def test_crosses_above_equal_then_cross_fires() -> None:
    """prev_lhs == prev_rhs AND curr_lhs > curr_rhs should fire
    CROSSES_ABOVE (canonical `<=` left side)."""
    cache = IndicatorCache()
    r = ref(IndicatorKind.SMA, 1)
    cache.register(r)
    cache.tick(candle(0, close="50"))  # prev = 50 (= rhs)
    cache.tick(candle(1, close="51"))  # curr = 51 > rhs
    cond = Condition(lhs=r, op=ComparatorOp.CROSSES_ABOVE, rhs=Decimal("50"))
    assert evaluate_condition(cond, cache) is True
