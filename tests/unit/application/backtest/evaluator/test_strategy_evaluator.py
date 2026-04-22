"""StrategyEvaluator.tick -> SignalTick(entry, exit) AND/OR-folded."""

from __future__ import annotations

from decimal import Decimal

import pandas as pd

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
    IndicatorRef,
    StrategyEntry,
    StrategyExit,
    StrategySpec,
)
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.domain.venues import MarketType, VenueId


def _symbol() -> Symbol:
    return Symbol(
        venue=VenueId.KUCOIN,
        base="BTC",
        quote="USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )


def _spec_with_conditions(
    *,
    entry_conds: tuple,
    exit_conds: tuple,
    tp: Decimal | None = None,
    sl: Decimal | None = None,
) -> StrategySpec:
    return StrategySpec(
        name="test",
        description="d",
        venue=VenueId.KUCOIN,
        symbol=_symbol(),
        timeframe=Timeframe.H1,
        entry=StrategyEntry(side=StrategySide.LONG, conditions=entry_conds),
        exit=StrategyExit(conditions=exit_conds, take_profit_pct=tp, stop_loss_pct=sl),
        size_pct=Decimal("0.25"),
    )


_REF = IndicatorRef(kind=IndicatorKind.SMA, period=1)


def test_tick_returns_signal_tick() -> None:
    spec = _spec_with_conditions(
        entry_conds=(Condition(lhs=_REF, op=ComparatorOp.GT, rhs=Decimal("50")),),
        exit_conds=(Condition(lhs=_REF, op=ComparatorOp.LT, rhs=Decimal("50")),),
    )
    evalr = StrategyEvaluator(spec, {_REF: pd.Series([100.0], dtype="float64")})
    tick = evalr.tick(0)
    assert tick == SignalTick(bar_index=0, entry_signal=True, exit_signal=False)


def test_and_fold_entry_multi_condition() -> None:
    spec = _spec_with_conditions(
        entry_conds=(
            Condition(lhs=_REF, op=ComparatorOp.GT, rhs=Decimal("50")),
            Condition(lhs=_REF, op=ComparatorOp.LT, rhs=Decimal("200")),
        ),
        exit_conds=(),
        tp=Decimal("0.05"),
    )
    evalr = StrategyEvaluator(spec, {_REF: pd.Series([100.0, 40.0, 300.0], dtype="float64")})
    assert evalr.tick(0).entry_signal is True  # 100 in (50, 200)
    assert evalr.tick(1).entry_signal is False  # 40 < 50
    assert evalr.tick(2).entry_signal is False  # 300 > 200


def test_or_fold_exit() -> None:
    spec = _spec_with_conditions(
        entry_conds=(Condition(lhs=_REF, op=ComparatorOp.GT, rhs=Decimal("0")),),
        exit_conds=(
            Condition(lhs=_REF, op=ComparatorOp.LT, rhs=Decimal("10")),
            Condition(lhs=_REF, op=ComparatorOp.GT, rhs=Decimal("1000")),
        ),
    )
    evalr = StrategyEvaluator(spec, {_REF: pd.Series([5.0, 500.0, 2000.0], dtype="float64")})
    assert evalr.tick(0).exit_signal is True  # 5 < 10
    assert evalr.tick(1).exit_signal is False  # neither branch
    assert evalr.tick(2).exit_signal is True  # 2000 > 1000


def test_exit_with_zero_conditions_emits_false() -> None:
    """TP/SL-only exit: exit_signal must be False (not None) so simulator
    knows TP/SL is the only way out."""
    spec = _spec_with_conditions(
        entry_conds=(Condition(lhs=_REF, op=ComparatorOp.GT, rhs=Decimal("0")),),
        exit_conds=(),
        tp=Decimal("0.05"),
    )
    evalr = StrategyEvaluator(spec, {_REF: pd.Series([10.0], dtype="float64")})
    assert evalr.tick(0).exit_signal is False


def test_none_propagates_on_warmup() -> None:
    spec = _spec_with_conditions(
        entry_conds=(Condition(lhs=_REF, op=ComparatorOp.GT, rhs=Decimal("0")),),
        exit_conds=(),
        tp=Decimal("0.05"),
    )
    evalr = StrategyEvaluator(spec, {_REF: pd.Series([float("nan"), 10.0], dtype="float64")})
    tick0 = evalr.tick(0)
    assert tick0.entry_signal is None
    assert tick0.exit_signal is False  # no exit conditions so False regardless
    tick1 = evalr.tick(1)
    assert tick1.entry_signal is True
