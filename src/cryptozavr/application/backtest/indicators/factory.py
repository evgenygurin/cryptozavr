"""IndicatorFactory: IndicatorRef -> computed pd.Series.

`compute_all(spec, df)` walks entry + exit conditions, collects unique
IndicatorRef instances (Pydantic frozen model — hashable), and invokes
each indicator once. Returns a dict keyed by ref.
"""

from __future__ import annotations

import pandas as pd

from cryptozavr.application.backtest.indicators.atr import AverageTrueRange
from cryptozavr.application.backtest.indicators.base import Indicator
from cryptozavr.application.backtest.indicators.ema import ExponentialMovingAverage
from cryptozavr.application.backtest.indicators.macd import MACD
from cryptozavr.application.backtest.indicators.rsi import RelativeStrengthIndex
from cryptozavr.application.backtest.indicators.sma import SimpleMovingAverage
from cryptozavr.application.backtest.indicators.volume import VolumeIndicator
from cryptozavr.application.strategy.enums import IndicatorKind
from cryptozavr.application.strategy.strategy_spec import (
    Condition,
    IndicatorRef,
    StrategySpec,
)


def create_indicator(ref: IndicatorRef) -> Indicator:
    if ref.kind is IndicatorKind.SMA:
        return SimpleMovingAverage(period=ref.period, source=ref.source)
    if ref.kind is IndicatorKind.EMA:
        return ExponentialMovingAverage(period=ref.period, source=ref.source)
    if ref.kind is IndicatorKind.RSI:
        return RelativeStrengthIndex(period=ref.period, source=ref.source)
    if ref.kind is IndicatorKind.MACD:
        return MACD(fast=12, slow=ref.period, source=ref.source)
    if ref.kind is IndicatorKind.ATR:
        return AverageTrueRange(period=ref.period)
    if ref.kind is IndicatorKind.VOLUME:
        return VolumeIndicator()
    raise ValueError(f"unhandled IndicatorKind: {ref.kind!r}")


def _collect_refs_from_conditions(
    conditions: tuple[Condition, ...],
) -> list[IndicatorRef]:
    refs: list[IndicatorRef] = []
    for c in conditions:
        refs.append(c.lhs)
        if isinstance(c.rhs, IndicatorRef):
            refs.append(c.rhs)
    return refs


def compute_all(spec: StrategySpec, df: pd.DataFrame) -> dict[IndicatorRef, pd.Series]:
    all_refs: list[IndicatorRef] = [
        *_collect_refs_from_conditions(spec.entry.conditions),
        *_collect_refs_from_conditions(spec.exit.conditions),
    ]
    unique: dict[IndicatorRef, pd.Series] = {}
    for ref in all_refs:
        if ref not in unique:
            unique[ref] = create_indicator(ref).compute(df)
    return unique
