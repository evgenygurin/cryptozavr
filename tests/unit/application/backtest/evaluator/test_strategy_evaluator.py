"""StrategyEvaluator: end-to-end signal generation from a StrategySpec."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.backtest.evaluator.signals import SignalTick
from cryptozavr.application.backtest.evaluator.strategy_evaluator import (
    StrategyEvaluator,
)
from cryptozavr.application.strategy.enums import (
    ComparatorOp,
    IndicatorKind,
    StrategySide,
)
from cryptozavr.application.strategy.strategy_spec import (
    Condition,
    StrategyEntry,
    StrategyExit,
    StrategySpec,
)
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.domain.venues import VenueId
from tests.unit.application.backtest.evaluator.fixtures import (
    _symbol,
    ema_crossover_spec,
    ref,
)
from tests.unit.application.backtest.indicators.fixtures import candle


def test_signal_tick_before_warm_up_is_none() -> None:
    spec = ema_crossover_spec(fast_period=2, slow_period=3)
    evalr = StrategyEvaluator(spec)
    tick = evalr.tick(candle(0, close="100"))
    assert tick == SignalTick(bar_index=0, entry_signal=None, exit_signal=None)


def test_entry_signal_true_on_crossover_bar() -> None:
    """Fast EMA crossing above slow EMA emits entry=True at the crossing bar."""
    spec = ema_crossover_spec(fast_period=2, slow_period=3)
    evalr = StrategyEvaluator(spec)
    # Trending up: fast crosses above slow early.
    closes = ["100", "95", "90", "100", "110", "120"]
    entries = []
    for i, c in enumerate(closes):
        t = evalr.tick(candle(i, close=c))
        entries.append(t.entry_signal)
    # Expect at least one True among the late bars (after both EMAs warm).
    assert any(e is True for e in entries)


def test_same_ref_entry_and_exit_shares_stream() -> None:
    """EMA(2) appearing in both entry and exit conditions uses the same
    Indicator instance — the cache interns the ref."""
    spec = ema_crossover_spec(fast_period=2, slow_period=3)
    evalr = StrategyEvaluator(spec)
    # The cache must contain only 2 indicators (fast + slow), not 4.
    registered = len(evalr.indicator_cache._indicators)
    assert registered == 2


def test_bar_index_increments() -> None:
    spec = ema_crossover_spec(fast_period=2, slow_period=3)
    evalr = StrategyEvaluator(spec)
    for i in range(5):
        t = evalr.tick(candle(i, close="100"))
        assert t.bar_index == i


def test_is_warm_transitions_at_slow_ema() -> None:
    spec = ema_crossover_spec(fast_period=2, slow_period=5)
    evalr = StrategyEvaluator(spec)
    for i in range(4):
        evalr.tick(candle(i, close=str(100 + i)))
    assert evalr.is_warm is False
    evalr.tick(candle(4, close="105"))
    assert evalr.is_warm is True


def test_exit_with_no_conditions_emits_false_not_none() -> None:
    """A strategy with TP/SL-only exit has `conditions=()` — the exit
    signal should be False ('no condition-based exit'), not None
    ('warming up'), once indicators are warm."""
    spec = StrategySpec(
        name="tp_sl_only",
        description="exit via TP/SL only",
        venue=VenueId.KUCOIN,
        symbol=_symbol(),
        timeframe=Timeframe.H1,
        entry=StrategyEntry(
            side=StrategySide.LONG,
            conditions=(
                Condition(
                    lhs=ref(IndicatorKind.SMA, 2),
                    op=ComparatorOp.GT,
                    rhs=Decimal("0"),
                ),
            ),
        ),
        exit=StrategyExit(
            conditions=(),
            take_profit_pct=Decimal("0.05"),
            stop_loss_pct=Decimal("0.02"),
        ),
        size_pct=Decimal("0.25"),
    )
    evalr = StrategyEvaluator(spec)
    evalr.tick(candle(0, close="100"))
    tick = evalr.tick(candle(1, close="100"))
    # Warm entry should produce True; exit_signal is False (no conditions).
    assert tick.exit_signal is False


def test_exit_condition_fires_on_reverse_crossover() -> None:
    spec = ema_crossover_spec(fast_period=2, slow_period=3)
    evalr = StrategyEvaluator(spec)
    # Trend up then down to trigger both the entry crossover and the exit.
    closes = ["100", "90", "80", "95", "110", "115", "100", "90", "80"]
    exits = []
    for i, c in enumerate(closes):
        t = evalr.tick(candle(i, close=c))
        exits.append(t.exit_signal)
    assert any(e is True for e in exits)


def test_and_fold_for_multi_condition_entry() -> None:
    """Entry with 2 conditions AND-ed: both must be True to emit True."""
    r = ref(IndicatorKind.SMA, 1)
    spec = StrategySpec(
        name="double_gate",
        description="two gates",
        venue=VenueId.KUCOIN,
        symbol=_symbol(),
        timeframe=Timeframe.H1,
        entry=StrategyEntry(
            side=StrategySide.LONG,
            conditions=(
                Condition(lhs=r, op=ComparatorOp.GT, rhs=Decimal("50")),
                Condition(lhs=r, op=ComparatorOp.LT, rhs=Decimal("200")),
            ),
        ),
        exit=StrategyExit(conditions=(), take_profit_pct=Decimal("0.05")),
        size_pct=Decimal("0.1"),
    )
    evalr = StrategyEvaluator(spec)
    # price in (50, 200) — both conditions pass
    tick = evalr.tick(candle(0, close="100"))
    assert tick.entry_signal is True
    # price <= 50 — first fails
    tick = evalr.tick(candle(1, close="40"))
    assert tick.entry_signal is False
    # price >= 200 — second fails
    tick = evalr.tick(candle(2, close="300"))
    assert tick.entry_signal is False


def test_evaluator_does_not_mutate_spec() -> None:
    spec = ema_crossover_spec()
    original_entry = spec.entry
    evalr = StrategyEvaluator(spec)
    for i in range(30):
        evalr.tick(candle(i, close=str(100 + i)))
    assert spec.entry is original_entry
