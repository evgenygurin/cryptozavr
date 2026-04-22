"""BacktestReport DTO + supporting value types for post-backtest analytics."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from cryptozavr.domain.exceptions import ValidationError
from cryptozavr.domain.value_objects import Instant, TimeRange


class TradeSide(StrEnum):
    LONG = "long"
    SHORT = "short"


@dataclass(frozen=True, slots=True)
class BacktestTrade:
    opened_at: Instant
    closed_at: Instant
    side: TradeSide
    entry_price: Decimal
    exit_price: Decimal
    size: Decimal
    pnl: Decimal

    def __post_init__(self) -> None:
        if self.closed_at.to_ms() < self.opened_at.to_ms():
            raise ValidationError("BacktestTrade: closed_at must be >= opened_at")
        if self.size <= 0:
            raise ValidationError("BacktestTrade: size must be > 0")


@dataclass(frozen=True, slots=True)
class EquityPoint:
    observed_at: Instant
    equity: Decimal


@dataclass(frozen=True, slots=True)
class BacktestReport:
    strategy_name: str
    period: TimeRange
    initial_equity: Decimal
    final_equity: Decimal
    trades: tuple[BacktestTrade, ...]
    equity_curve: tuple[EquityPoint, ...]

    def __post_init__(self) -> None:
        if self.initial_equity <= 0:
            raise ValidationError("BacktestReport: initial_equity must be > 0")
        for a, b in zip(self.trades, self.trades[1:], strict=False):
            if b.opened_at.to_ms() < a.opened_at.to_ms():
                raise ValidationError(
                    "BacktestReport: trades must be sorted by opened_at ascending",
                )
