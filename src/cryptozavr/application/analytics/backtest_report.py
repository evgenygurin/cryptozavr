"""BacktestReport DTO + supporting value types for post-backtest analytics.

Invariants enforced at construction:
- `BacktestTrade`: chronology (`closed_at >= opened_at`), positive size,
  finite prices + pnl, pnl sign consistent with side/entry/exit.
- `EquityPoint`: finite equity (NaN/±inf rejected).
- `BacktestReport`: `initial_equity > 0`; `trades` + `equity_curve` both
  sorted chronologically; `equity_curve[0].equity == initial_equity` and
  `equity_curve[-1].equity == final_equity` when the curve is non-empty.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from cryptozavr.domain.exceptions import ValidationError
from cryptozavr.domain.value_objects import Instant, TimeRange


class PositionSide(StrEnum):
    """Long/short side of a backtest trade (distinct from `domain.TradeSide` which
    tracks taker direction of an individual tick)."""

    LONG = "long"
    SHORT = "short"


# Backwards-compatible alias — first consumers (tests, spec) used `TradeSide`.
TradeSide = PositionSide


@dataclass(frozen=True, slots=True)
class BacktestTrade:
    opened_at: Instant
    closed_at: Instant
    side: PositionSide
    entry_price: Decimal
    exit_price: Decimal
    size: Decimal
    pnl: Decimal

    def __post_init__(self) -> None:
        if self.closed_at.to_ms() < self.opened_at.to_ms():
            raise ValidationError("BacktestTrade: closed_at must be >= opened_at")
        if self.size <= 0:
            raise ValidationError("BacktestTrade: size must be > 0")
        for name, value in (
            ("entry_price", self.entry_price),
            ("exit_price", self.exit_price),
            ("pnl", self.pnl),
        ):
            if not value.is_finite():
                raise ValidationError(f"BacktestTrade.{name} must be finite (got {value!r})")
        if self.entry_price <= 0 or self.exit_price <= 0:
            raise ValidationError("BacktestTrade: entry_price and exit_price must be > 0")
        expected_sign = (
            (self.exit_price - self.entry_price)
            if self.side is PositionSide.LONG
            else (self.entry_price - self.exit_price)
        )
        # Sign-only check — fee models can shrink pnl magnitude, so we don't
        # demand exact equality to (price_delta * size). Catches the most
        # common class of bug: pnl computed with wrong side.
        if (expected_sign > 0 and self.pnl < 0) or (expected_sign < 0 and self.pnl > 0):
            raise ValidationError(
                f"BacktestTrade: pnl sign contradicts side/prices "
                f"(side={self.side}, entry={self.entry_price}, exit={self.exit_price}, pnl={self.pnl})"
            )


@dataclass(frozen=True, slots=True)
class EquityPoint:
    observed_at: Instant
    equity: Decimal

    def __post_init__(self) -> None:
        if not self.equity.is_finite():
            raise ValidationError(f"EquityPoint.equity must be finite (got {self.equity!r})")


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
        if not self.final_equity.is_finite():
            raise ValidationError("BacktestReport.final_equity must be finite")
        # Trades chronology — strict=False because `trades[1:]` is shorter
        # by construction (pairwise comparison over n/n-1 slice).
        for a, b in zip(self.trades, self.trades[1:], strict=False):
            if b.opened_at.to_ms() < a.opened_at.to_ms():
                raise ValidationError(
                    "BacktestReport: trades must be sorted by opened_at ascending",
                )
        for ep_a, ep_b in zip(self.equity_curve, self.equity_curve[1:], strict=False):
            if ep_b.observed_at.to_ms() < ep_a.observed_at.to_ms():
                raise ValidationError(
                    "BacktestReport: equity_curve must be sorted by observed_at ascending",
                )
        # Cross-field consistency: the curve's endpoints must agree with
        # initial/final equity so visitors reading either source don't
        # disagree.
        if self.equity_curve:
            if self.equity_curve[0].equity != self.initial_equity:
                raise ValidationError(
                    "BacktestReport: equity_curve[0].equity must equal initial_equity",
                )
            if self.equity_curve[-1].equity != self.final_equity:
                raise ValidationError(
                    "BacktestReport: equity_curve[-1].equity must equal final_equity",
                )
