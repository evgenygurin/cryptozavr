"""Canonical valid StrategySpec for tests that don't care about fields."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

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


def btc_usdt_spot() -> Symbol:
    """Canonical test instrument — KuCoin BTC/USDT spot."""
    return Symbol(
        venue=VenueId.KUCOIN,
        base="BTC",
        quote="USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )


def _ref(kind: IndicatorKind = IndicatorKind.SMA, period: int = 20) -> IndicatorRef:
    return IndicatorRef(kind=kind, period=period)


def valid_spec(**overrides: Any) -> StrategySpec:
    base: dict[str, Any] = {
        "name": "test_strategy",
        "description": "moving-average crossover with ATR stop",
        "venue": VenueId.KUCOIN,
        "symbol": btc_usdt_spot(),
        "timeframe": Timeframe.H1,
        "entry": StrategyEntry(
            side=StrategySide.LONG,
            conditions=(
                Condition(
                    lhs=_ref(IndicatorKind.EMA, 12),
                    op=ComparatorOp.CROSSES_ABOVE,
                    rhs=_ref(IndicatorKind.EMA, 26),
                ),
            ),
        ),
        "exit": StrategyExit(
            conditions=(
                Condition(
                    lhs=_ref(IndicatorKind.EMA, 12),
                    op=ComparatorOp.CROSSES_BELOW,
                    rhs=_ref(IndicatorKind.EMA, 26),
                ),
            ),
            take_profit_pct=Decimal("0.05"),
            stop_loss_pct=Decimal("0.02"),
        ),
        "size_pct": Decimal("0.25"),
    }
    base.update(overrides)
    return StrategySpec(**base)
