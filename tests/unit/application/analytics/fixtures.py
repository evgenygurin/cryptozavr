"""Hand-built BacktestReport fixtures for visitor tests."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.analytics.backtest_report import (
    BacktestReport,
    BacktestTrade,
    EquityPoint,
    TradeSide,
)
from cryptozavr.domain.value_objects import Instant, TimeRange

_DAY_MS = 86_400_000


def _point(day: int, equity: str) -> EquityPoint:
    return EquityPoint(
        observed_at=Instant.from_ms(1_700_000_000_000 + day * _DAY_MS),
        equity=Decimal(equity),
    )


def _trade(day: int, pnl: str, *, size: str = "1") -> BacktestTrade:
    open_ms = 1_700_000_000_000 + day * _DAY_MS
    return BacktestTrade(
        opened_at=Instant.from_ms(open_ms),
        closed_at=Instant.from_ms(open_ms + 60_000),
        side=TradeSide.LONG,
        entry_price=Decimal("100"),
        exit_price=Decimal("100") + Decimal(pnl),
        size=Decimal(size),
        pnl=Decimal(pnl),
    )


def make_report(
    *,
    initial: str | None = None,
    final: str | None = None,
    equity_curve: tuple[str, ...] = ("1000", "1050", "1100"),
    trades: tuple[BacktestTrade, ...] = (),
) -> BacktestReport:
    # Keep fixture consistent with BacktestReport's cross-field invariants:
    # if a curve is supplied, initial/final default to its endpoints.
    if equity_curve:
        initial = initial if initial is not None else equity_curve[0]
        final = final if final is not None else equity_curve[-1]
    else:
        initial = initial if initial is not None else "1000"
        final = final if final is not None else initial
    last_day = max(len(equity_curve), 1)
    return BacktestReport(
        strategy_name="test",
        period=TimeRange(
            start=Instant.from_ms(1_700_000_000_000),
            end=Instant.from_ms(1_700_000_000_000 + last_day * _DAY_MS),
        ),
        initial_equity=Decimal(initial),
        final_equity=Decimal(final),
        trades=trades,
        equity_curve=tuple(_point(i, v) for i, v in enumerate(equity_curve)),
    )
