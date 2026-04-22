"""create_indicator + compute_all: IndicatorRef -> computed pd.Series."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.backtest.indicators.atr import AverageTrueRange
from cryptozavr.application.backtest.indicators.ema import ExponentialMovingAverage
from cryptozavr.application.backtest.indicators.factory import (
    compute_all,
    create_indicator,
)
from cryptozavr.application.backtest.indicators.macd import MACD
from cryptozavr.application.backtest.indicators.rsi import RelativeStrengthIndex
from cryptozavr.application.backtest.indicators.sma import SimpleMovingAverage
from cryptozavr.application.backtest.indicators.volume import VolumeIndicator
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
from tests.unit.application.backtest.fixtures import candle_df


def _symbol() -> Symbol:
    return Symbol(
        venue=VenueId.KUCOIN,
        base="BTC",
        quote="USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )


def test_sma_ref_creates_sma() -> None:
    ind = create_indicator(IndicatorRef(kind=IndicatorKind.SMA, period=20))
    assert isinstance(ind, SimpleMovingAverage)
    assert ind.period == 20


def test_ema_ref_creates_ema() -> None:
    assert isinstance(
        create_indicator(IndicatorRef(kind=IndicatorKind.EMA, period=12)),
        ExponentialMovingAverage,
    )


def test_rsi_ref_creates_rsi() -> None:
    assert isinstance(
        create_indicator(IndicatorRef(kind=IndicatorKind.RSI, period=14)),
        RelativeStrengthIndex,
    )


def test_macd_ref_creates_macd_slow_from_period() -> None:
    ind = create_indicator(IndicatorRef(kind=IndicatorKind.MACD, period=26))
    assert isinstance(ind, MACD)
    assert ind.period == 26


def test_atr_ref_creates_atr() -> None:
    assert isinstance(
        create_indicator(IndicatorRef(kind=IndicatorKind.ATR, period=14)),
        AverageTrueRange,
    )


def test_volume_ref_creates_volume() -> None:
    assert isinstance(
        create_indicator(IndicatorRef(kind=IndicatorKind.VOLUME, period=1)),
        VolumeIndicator,
    )


def test_compute_all_interns_same_ref_once() -> None:
    """A spec referencing the same IndicatorRef in entry + exit must yield
    exactly one Series (interning)."""
    fast = IndicatorRef(kind=IndicatorKind.EMA, period=12)
    slow = IndicatorRef(kind=IndicatorKind.EMA, period=26)
    spec = StrategySpec(
        name="crossover",
        description="d",
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
        ),
        size_pct=Decimal("0.25"),
    )
    df = candle_df([str(100 + i) for i in range(30)])
    series_map = compute_all(spec, df)
    assert set(series_map.keys()) == {fast, slow}  # exactly 2 unique refs
    assert len(series_map[fast]) == 30
