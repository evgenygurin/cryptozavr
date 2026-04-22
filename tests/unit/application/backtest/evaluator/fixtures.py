"""Builder helpers for evaluator tests."""

from __future__ import annotations

from decimal import Decimal

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


def ref(kind: IndicatorKind, period: int) -> IndicatorRef:
    return IndicatorRef(kind=kind, period=period)


def _symbol() -> Symbol:
    return Symbol(
        venue=VenueId.KUCOIN,
        base="BTC",
        quote="USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )


def ema_crossover_spec(
    *,
    fast_period: int = 12,
    slow_period: int = 26,
) -> StrategySpec:
    fast = ref(IndicatorKind.EMA, fast_period)
    slow = ref(IndicatorKind.EMA, slow_period)
    return StrategySpec(
        name="crossover",
        description="EMA fast crossing slow",
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
