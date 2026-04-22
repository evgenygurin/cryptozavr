"""TradeSimulator: per-bar position lifecycle with slippage + fees."""

from __future__ import annotations

from decimal import Decimal

import pandas as pd

from cryptozavr.application.backtest.evaluator.signals import SignalTick
from cryptozavr.application.backtest.simulator.fees import FixedBpsFeeModel
from cryptozavr.application.backtest.simulator.slippage import PctSlippageModel
from cryptozavr.application.backtest.simulator.trade_simulator import TradeSimulator
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


def _spec(
    *,
    tp: Decimal | None = Decimal("0.05"),
    sl: Decimal | None = Decimal("0.02"),
    size_pct: Decimal = Decimal("0.5"),
    side: StrategySide = StrategySide.LONG,
) -> StrategySpec:
    ref = IndicatorRef(kind=IndicatorKind.SMA, period=1)
    return StrategySpec(
        name="t",
        description="d",
        venue=VenueId.KUCOIN,
        symbol=_symbol(),
        timeframe=Timeframe.H1,
        entry=StrategyEntry(
            side=side,
            conditions=(Condition(lhs=ref, op=ComparatorOp.GT, rhs=Decimal("0")),),
        ),
        exit=StrategyExit(
            conditions=(),
            take_profit_pct=tp,
            stop_loss_pct=sl,
        ),
        size_pct=size_pct,
    )


def _row(open_: str, high: str, low: str, close: str, volume: str = "1000") -> pd.Series:
    return pd.Series(
        {
            "open": float(open_),
            "high": float(high),
            "low": float(low),
            "close": float(close),
            "volume": float(volume),
        }
    )


def test_initial_state_no_position_no_trades() -> None:
    sim = TradeSimulator(
        _spec(),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    assert sim.open_position is None
    assert sim.trades == ()
    assert sim.equity == Decimal("10000")


def test_entry_signal_opens_long_position_frictionless() -> None:
    sim = TradeSimulator(
        _spec(size_pct=Decimal("0.5")),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    sim.tick(
        _row("100", "101", "99", "100"),
        SignalTick(bar_index=0, entry_signal=True, exit_signal=False),
    )
    assert sim.open_position is not None
    assert sim.open_position.side is StrategySide.LONG
    # size = 0.5 * 10000 / 100 = 50
    assert sim.open_position.size == Decimal("50")
    # TP level = 100 * 1.05 = 105; SL level = 100 * 0.98 = 98
    assert sim.open_position.take_profit_level == Decimal("105.00")
    assert sim.open_position.stop_loss_level == Decimal("98.00")


def test_entry_signal_without_signal_stays_flat() -> None:
    sim = TradeSimulator(
        _spec(),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    sim.tick(
        _row("100", "101", "99", "100"),
        SignalTick(bar_index=0, entry_signal=None, exit_signal=False),
    )
    assert sim.open_position is None
    assert sim.equity_curve[0].equity == Decimal("10000")


def test_tp_hit_closes_long_at_tp_level() -> None:
    sim = TradeSimulator(
        _spec(tp=Decimal("0.05"), sl=None),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    sim.tick(
        _row("100", "101", "99", "100"),
        SignalTick(bar_index=0, entry_signal=True, exit_signal=False),
    )
    # Bar 1: high = 106, above TP=105 → TP fires.
    sim.tick(
        _row("101", "106", "100", "103"),
        SignalTick(bar_index=1, entry_signal=False, exit_signal=False),
    )
    assert sim.open_position is None
    assert len(sim.trades) == 1
    # pnl = (105 - 100) * 50 = 250
    assert sim.trades[0].pnl == Decimal("250.00")
    assert sim.trades[0].exit_price == Decimal("105.00")


def test_sl_hit_closes_long_at_sl_level() -> None:
    sim = TradeSimulator(
        _spec(tp=None, sl=Decimal("0.02")),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    sim.tick(
        _row("100", "101", "99", "100"),
        SignalTick(bar_index=0, entry_signal=True, exit_signal=False),
    )
    # Bar 1: low = 97, below SL=98 → SL fires.
    sim.tick(
        _row("100", "101", "97", "98"),
        SignalTick(bar_index=1, entry_signal=False, exit_signal=False),
    )
    assert len(sim.trades) == 1
    # pnl = (98 - 100) * 50 = -100
    assert sim.trades[0].pnl == Decimal("-100.00")
    assert sim.trades[0].exit_price == Decimal("98.00")


def test_tp_and_sl_both_inside_worst_case_long_sl_wins() -> None:
    sim = TradeSimulator(
        _spec(tp=Decimal("0.05"), sl=Decimal("0.02")),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    sim.tick(
        _row("100", "101", "99", "100"),
        SignalTick(bar_index=0, entry_signal=True, exit_signal=False),
    )
    # Bar 1: low=97 (< SL=98), high=107 (> TP=105). Both inside.
    # Worst-case-first for LONG: SL wins.
    sim.tick(
        _row("100", "107", "97", "101"),
        SignalTick(bar_index=1, entry_signal=False, exit_signal=False),
    )
    assert sim.trades[0].exit_price == Decimal("98.00")


def test_exit_signal_closes_at_close_price() -> None:
    """With condition-based exit (not TP/SL), position closes at bar close."""
    ref = IndicatorRef(kind=IndicatorKind.SMA, period=1)
    spec = StrategySpec(
        name="t",
        description="d",
        venue=VenueId.KUCOIN,
        symbol=_symbol(),
        timeframe=Timeframe.H1,
        entry=StrategyEntry(
            side=StrategySide.LONG,
            conditions=(Condition(lhs=ref, op=ComparatorOp.GT, rhs=Decimal("0")),),
        ),
        exit=StrategyExit(
            conditions=(Condition(lhs=ref, op=ComparatorOp.LT, rhs=Decimal("0")),),
        ),
        size_pct=Decimal("0.5"),
    )
    sim = TradeSimulator(
        spec,
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    sim.tick(
        _row("100", "101", "99", "100"),
        SignalTick(bar_index=0, entry_signal=True, exit_signal=False),
    )
    sim.tick(
        _row("100", "105", "99", "104"),
        SignalTick(bar_index=1, entry_signal=False, exit_signal=True),
    )
    assert len(sim.trades) == 1
    # Closed at close=104, entry=100, size=50 → pnl = 4 * 50 = 200
    assert sim.trades[0].exit_price == Decimal("104")
    assert sim.trades[0].pnl == Decimal("200")


def test_dust_trade_skipped_zero_size() -> None:
    sim = TradeSimulator(
        _spec(size_pct=Decimal("0.0000000001")),
        initial_equity=Decimal("10"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    # At price 1e18 size rounds to 0 — skip
    sim.tick(
        _row(
            "1000000000000000000",
            "1000000000000000000",
            "1000000000000000000",
            "1000000000000000000",
        ),
        SignalTick(bar_index=0, entry_signal=True, exit_signal=False),
    )
    assert sim.open_position is None


def test_min_notional_skips_small_trade() -> None:
    sim = TradeSimulator(
        _spec(size_pct=Decimal("0.001")),
        initial_equity=Decimal("100"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
        min_notional=Decimal("10"),
    )
    # size_pct * equity = 0.1 < min_notional = 10 → skip
    sim.tick(
        _row("100", "101", "99", "100"),
        SignalTick(bar_index=0, entry_signal=True, exit_signal=False),
    )
    assert sim.open_position is None


def test_fees_reduce_pnl() -> None:
    sim = TradeSimulator(
        _spec(tp=Decimal("0.05"), sl=None),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=10),  # 10 bps = 0.001 = 0.1%
    )
    sim.tick(
        _row("100", "101", "99", "100"),
        SignalTick(bar_index=0, entry_signal=True, exit_signal=False),
    )
    sim.tick(
        _row("101", "106", "100", "103"),
        SignalTick(bar_index=1, entry_signal=False, exit_signal=False),
    )
    # Entry fee: size=50, entry_price=100, notional=5000, fee=5
    # Exit fee: exit_price=105, notional=5250, fee=5.25
    # Gross pnl = 250. Fees = 10.25. Net = 239.75.
    assert sim.trades[0].pnl == Decimal("239.75")


def test_short_position_pnl_sign() -> None:
    sim = TradeSimulator(
        _spec(side=StrategySide.SHORT, tp=Decimal("0.05"), sl=None),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    sim.tick(
        _row("100", "101", "99", "100"),
        SignalTick(bar_index=0, entry_signal=True, exit_signal=False),
    )
    # Price falls → short profits. TP for short is 100 * 0.95 = 95.
    sim.tick(
        _row("98", "98", "94", "95"),
        SignalTick(bar_index=1, entry_signal=False, exit_signal=False),
    )
    # entry=100, exit=95, size=50 → pnl for SHORT = (100 - 95) * 50 = 250
    assert sim.trades[0].pnl == Decimal("250.00")


def test_equity_curve_length_matches_bars() -> None:
    sim = TradeSimulator(
        _spec(),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    for i in range(5):
        sim.tick(
            _row("100", "101", "99", "100"),
            SignalTick(bar_index=i, entry_signal=None, exit_signal=False),
        )
    assert len(sim.equity_curve) == 5


def test_position_still_open_closed_externally() -> None:
    """Simulator does not auto-close at series end — caller (engine) does."""
    sim = TradeSimulator(
        _spec(),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    sim.tick(
        _row("100", "101", "99", "100"),
        SignalTick(bar_index=0, entry_signal=True, exit_signal=False),
    )
    assert sim.open_position is not None
    # caller uses close_open_position to flush at end
    sim.close_open_position(close_price=Decimal("103"), bar_index=0)
    assert sim.open_position is None
    assert len(sim.trades) == 1
    assert sim.trades[0].exit_price == Decimal("103")
