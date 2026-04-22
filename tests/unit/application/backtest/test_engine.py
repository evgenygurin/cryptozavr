"""BacktestEngine.run: candles + spec -> BacktestReport."""

from __future__ import annotations

from decimal import Decimal

import pandas as pd
import pytest

from cryptozavr.application.analytics.backtest_report import BacktestReport
from cryptozavr.application.backtest.engine import BacktestEngine
from cryptozavr.application.backtest.simulator.fees import FixedBpsFeeModel
from cryptozavr.application.backtest.simulator.slippage import PctSlippageModel
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
from cryptozavr.domain.exceptions import ValidationError
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.domain.venues import MarketType, VenueId
from tests.unit.application.backtest.fixtures import candle_df


def _symbol() -> Symbol:
    return Symbol(
        venue=VenueId.KUCOIN,
        base="BTC",
        quote="USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )


def _tp_sl_spec() -> StrategySpec:
    ref = IndicatorRef(kind=IndicatorKind.SMA, period=1)
    return StrategySpec(
        name="always",
        description="d",
        venue=VenueId.KUCOIN,
        symbol=_symbol(),
        timeframe=Timeframe.H1,
        entry=StrategyEntry(
            side=StrategySide.LONG,
            conditions=(Condition(lhs=ref, op=ComparatorOp.GT, rhs=Decimal("0")),),
        ),
        exit=StrategyExit(
            conditions=(),
            take_profit_pct=Decimal("0.05"),
            stop_loss_pct=Decimal("0.02"),
        ),
        size_pct=Decimal("0.5"),
    )


def test_run_returns_backtest_report() -> None:
    engine = BacktestEngine()
    report = engine.run(
        _tp_sl_spec(),
        candle_df(["100", "101", "102", "103"]),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    assert isinstance(report, BacktestReport)
    assert report.strategy_name == "always"
    assert report.initial_equity == Decimal("10000")


def test_run_raises_on_empty_candles() -> None:
    engine = BacktestEngine()
    with pytest.raises(ValidationError, match="empty"):
        engine.run(
            _tp_sl_spec(),
            pd.DataFrame(columns=["open", "high", "low", "close", "volume"]),
            initial_equity=Decimal("10000"),
        )


def test_run_raises_on_missing_columns() -> None:
    engine = BacktestEngine()
    bad = pd.DataFrame({"open": [1.0], "close": [1.0]})
    with pytest.raises(ValidationError, match="columns"):
        engine.run(_tp_sl_spec(), bad, initial_equity=Decimal("10000"))


def test_run_closes_open_position_at_end() -> None:
    engine = BacktestEngine()
    # TP = 5%, SL = 2%. Upward-drifting series that never hits either →
    # position remains open till end → engine closes it.
    df = candle_df(["100", "100.5", "101", "101.5"])
    report = engine.run(
        _tp_sl_spec(),
        df,
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    assert len(report.trades) >= 1  # at least the final auto-close
    # Final equity must be the last equity curve point.
    assert report.final_equity == report.equity_curve[-1].equity


def test_equity_curve_length_matches_candles() -> None:
    engine = BacktestEngine()
    df = candle_df(["100"] * 20)
    report = engine.run(
        _tp_sl_spec(),
        df,
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    assert len(report.equity_curve) == 20
