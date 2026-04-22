"""IndicatorFactory: IndicatorRef → concrete Indicator instance.

One factory call produces one fresh, stateful indicator. The caller owns
the instance and feeds it candles one-at-a-time.
"""

from __future__ import annotations

from cryptozavr.application.backtest.indicators.atr import AverageTrueRange
from cryptozavr.application.backtest.indicators.base import Indicator
from cryptozavr.application.backtest.indicators.ema import ExponentialMovingAverage
from cryptozavr.application.backtest.indicators.macd import MACD
from cryptozavr.application.backtest.indicators.rsi import RelativeStrengthIndex
from cryptozavr.application.backtest.indicators.sma import SimpleMovingAverage
from cryptozavr.application.backtest.indicators.volume import VolumeIndicator
from cryptozavr.application.strategy.enums import IndicatorKind
from cryptozavr.application.strategy.strategy_spec import IndicatorRef


def create_indicator(ref: IndicatorRef) -> Indicator:
    """Return a freshly-initialised streaming Indicator for this ref.

    MACD uses `ref.period` as the slow EMA period (fast=12, signal=9
    fixed — signal not exposed in 2B.1). ATR and VOLUME ignore
    `ref.source` (ATR operates on OHLC tuples; VOLUME reads the volume
    field directly).
    """
    match ref.kind:
        case IndicatorKind.SMA:
            return SimpleMovingAverage(period=ref.period, source=ref.source)
        case IndicatorKind.EMA:
            return ExponentialMovingAverage(period=ref.period, source=ref.source)
        case IndicatorKind.RSI:
            return RelativeStrengthIndex(period=ref.period, source=ref.source)
        case IndicatorKind.MACD:
            return MACD(fast=12, slow=ref.period, source=ref.source)
        case IndicatorKind.ATR:
            return AverageTrueRange(period=ref.period)
        case IndicatorKind.VOLUME:
            return VolumeIndicator()
