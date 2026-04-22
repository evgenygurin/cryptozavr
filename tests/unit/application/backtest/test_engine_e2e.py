"""End-to-end: realistic specs against synthetic series, 2C visitors
consume the produced BacktestReport."""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from cryptozavr.application.analytics.analytics_service import (
    BacktestAnalyticsService,
)
from cryptozavr.application.analytics.visitors.max_drawdown import MaxDrawdownVisitor
from cryptozavr.application.analytics.visitors.profit_factor import ProfitFactorVisitor
from cryptozavr.application.analytics.visitors.sharpe import SharpeRatioVisitor
from cryptozavr.application.analytics.visitors.total_return import TotalReturnVisitor
from cryptozavr.application.analytics.visitors.win_rate import WinRateVisitor
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


def _ema_crossover_spec() -> StrategySpec:
    fast = IndicatorRef(kind=IndicatorKind.EMA, period=3)
    slow = IndicatorRef(kind=IndicatorKind.EMA, period=8)
    return StrategySpec(
        name="crossover",
        description="EMA crossover",
        venue=VenueId.KUCOIN,
        symbol=_symbol(),
        timeframe=Timeframe.H1,
        entry=StrategyEntry(
            side=StrategySide.LONG,
            conditions=(Condition(lhs=fast, op=ComparatorOp.CROSSES_ABOVE, rhs=slow),),
        ),
        exit=StrategyExit(
            conditions=(Condition(lhs=fast, op=ComparatorOp.CROSSES_BELOW, rhs=slow),),
            take_profit_pct=Decimal("0.05"),
            stop_loss_pct=Decimal("0.02"),
        ),
        size_pct=Decimal("0.25"),
    )


def test_crossover_on_trending_series_makes_trades_and_visitors_run() -> None:
    engine = BacktestEngine()
    # Strong uptrend then pullback then uptrend — crossover should fire.
    closes = [str(100 + i) for i in range(5)]  # ramp
    closes += [str(105 - i) for i in range(1, 6)]  # pullback
    closes += [str(100 + i * 2) for i in range(1, 15)]  # ramp up more
    report = engine.run(
        _ema_crossover_spec(),
        candle_df(closes),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    assert len(report.trades) >= 1  # at least one trade
    # 2C visitors work against the produced report
    service = BacktestAnalyticsService(
        [
            TotalReturnVisitor(),
            WinRateVisitor(),
            MaxDrawdownVisitor(),
            ProfitFactorVisitor(),
            SharpeRatioVisitor(),
        ]
    )
    results = service.run_all(report)
    assert "total_return" in results
    assert "win_rate" in results
    assert "max_drawdown" in results
    assert "profit_factor" in results
    assert "sharpe_ratio" in results


def test_report_equity_curve_matches_candles_length() -> None:
    engine = BacktestEngine()
    closes = [str(100 + i) for i in range(30)]
    report = engine.run(
        _ema_crossover_spec(),
        candle_df(closes),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    assert len(report.equity_curve) == 30
    assert report.equity_curve[0].equity == Decimal("10000")


def test_flat_series_no_trades_zero_return() -> None:
    engine = BacktestEngine()
    report = engine.run(
        _ema_crossover_spec(),
        candle_df(["100"] * 20),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=0),
        fees=FixedBpsFeeModel(bps=0),
    )
    assert report.trades == ()
    assert report.final_equity == Decimal("10000")


def test_single_candle_rejected_by_engine() -> None:
    """Single-candle backtest is meaningless — engine rejects at validation."""
    engine = BacktestEngine()
    with pytest.raises(ValidationError, match="at least 2 candles"):
        engine.run(
            _ema_crossover_spec(),
            candle_df(["100"]),
            initial_equity=Decimal("10000"),
            slippage=PctSlippageModel(bps=0),
            fees=FixedBpsFeeModel(bps=0),
        )


@given(
    closes=st.lists(
        st.floats(min_value=50.0, max_value=200.0, allow_nan=False, allow_infinity=False),
        min_size=5,
        max_size=40,
    )
)
@settings(max_examples=25, deadline=None)
def test_property_bounded_series_never_raises(closes: list[float]) -> None:
    """Random bounded series + a standard spec → engine returns a valid
    BacktestReport and 2C visitors never raise."""
    engine = BacktestEngine()
    report = engine.run(
        _ema_crossover_spec(),
        candle_df([str(round(c, 4)) for c in closes]),
        initial_equity=Decimal("10000"),
        slippage=PctSlippageModel(bps=5),
        fees=FixedBpsFeeModel(bps=2),
    )
    service = BacktestAnalyticsService(
        [
            TotalReturnVisitor(),
            WinRateVisitor(),
            MaxDrawdownVisitor(),
            ProfitFactorVisitor(),
            SharpeRatioVisitor(),
        ]
    )
    results = service.run_all(report)
    for name, value in results.items():
        assert value is None or value.is_finite(), f"{name} returned non-finite {value!r}"
