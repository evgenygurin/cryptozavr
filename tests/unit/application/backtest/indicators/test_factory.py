"""IndicatorFactory: IndicatorRef → right concrete type, fresh instance."""

from __future__ import annotations

from cryptozavr.application.backtest.indicators.atr import AverageTrueRange
from cryptozavr.application.backtest.indicators.ema import ExponentialMovingAverage
from cryptozavr.application.backtest.indicators.factory import create_indicator
from cryptozavr.application.backtest.indicators.macd import MACD
from cryptozavr.application.backtest.indicators.rsi import RelativeStrengthIndex
from cryptozavr.application.backtest.indicators.sma import SimpleMovingAverage
from cryptozavr.application.backtest.indicators.volume import VolumeIndicator
from cryptozavr.application.strategy.enums import IndicatorKind
from cryptozavr.application.strategy.strategy_spec import IndicatorRef
from tests.unit.application.backtest.indicators.fixtures import candle


def test_sma_ref_creates_sma_instance() -> None:
    ind = create_indicator(IndicatorRef(kind=IndicatorKind.SMA, period=20))
    assert isinstance(ind, SimpleMovingAverage)
    assert ind.period == 20


def test_ema_ref_creates_ema_instance() -> None:
    ind = create_indicator(IndicatorRef(kind=IndicatorKind.EMA, period=12))
    assert isinstance(ind, ExponentialMovingAverage)


def test_rsi_ref_creates_rsi_instance() -> None:
    ind = create_indicator(IndicatorRef(kind=IndicatorKind.RSI, period=14))
    assert isinstance(ind, RelativeStrengthIndex)


def test_macd_ref_creates_macd_with_slow_from_period() -> None:
    ind = create_indicator(IndicatorRef(kind=IndicatorKind.MACD, period=26))
    assert isinstance(ind, MACD)
    assert ind.period == 26


def test_atr_ref_creates_atr_instance() -> None:
    ind = create_indicator(IndicatorRef(kind=IndicatorKind.ATR, period=14))
    assert isinstance(ind, AverageTrueRange)


def test_volume_ref_creates_volume_instance() -> None:
    ind = create_indicator(IndicatorRef(kind=IndicatorKind.VOLUME, period=1))
    assert isinstance(ind, VolumeIndicator)


def test_factory_returns_independent_instances() -> None:
    """Two factory calls with the same ref must produce instances that
    don't share state — one SMA accepting a bar must not affect the other."""
    ref = IndicatorRef(kind=IndicatorKind.SMA, period=2)
    a = create_indicator(ref)
    b = create_indicator(ref)
    assert a is not b
    a.update(candle(0, close="100"))
    # b hasn't seen any bars yet
    assert b.is_warm is False
