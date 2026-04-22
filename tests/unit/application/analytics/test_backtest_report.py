"""BacktestReport DTO validation."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.application.analytics.backtest_report import (
    BacktestReport,
    BacktestTrade,
    EquityPoint,
    TradeSide,
)
from cryptozavr.domain.exceptions import ValidationError
from cryptozavr.domain.value_objects import Instant, TimeRange


def _tr(start_ms: int = 1_700_000_000_000, end_ms: int = 1_700_086_400_000) -> TimeRange:
    return TimeRange(start=Instant.from_ms(start_ms), end=Instant.from_ms(end_ms))


class TestBacktestTrade:
    def test_accepts_positive_values(self) -> None:
        t = BacktestTrade(
            opened_at=Instant.from_ms(1_700_000_000_000),
            closed_at=Instant.from_ms(1_700_000_060_000),
            side=TradeSide.LONG,
            entry_price=Decimal("100"),
            exit_price=Decimal("110"),
            size=Decimal("1"),
            pnl=Decimal("10"),
        )
        assert t.pnl == Decimal("10")

    def test_rejects_closed_before_opened(self) -> None:
        with pytest.raises(ValidationError, match="closed_at must be >= opened_at"):
            BacktestTrade(
                opened_at=Instant.from_ms(1_700_000_060_000),
                closed_at=Instant.from_ms(1_700_000_000_000),
                side=TradeSide.LONG,
                entry_price=Decimal("100"),
                exit_price=Decimal("110"),
                size=Decimal("1"),
                pnl=Decimal("10"),
            )

    def test_rejects_non_positive_size(self) -> None:
        with pytest.raises(ValidationError, match="size must be > 0"):
            BacktestTrade(
                opened_at=Instant.from_ms(1_700_000_000_000),
                closed_at=Instant.from_ms(1_700_000_060_000),
                side=TradeSide.LONG,
                entry_price=Decimal("100"),
                exit_price=Decimal("110"),
                size=Decimal("0"),
                pnl=Decimal("0"),
            )


class TestBacktestReport:
    def test_accepts_valid_report(self) -> None:
        r = BacktestReport(
            strategy_name="vwap_mean_revert",
            period=_tr(),
            initial_equity=Decimal("1000"),
            final_equity=Decimal("1100"),
            trades=(),
            equity_curve=(
                EquityPoint(
                    observed_at=Instant.from_ms(1_700_000_000_000),
                    equity=Decimal("1000"),
                ),
                EquityPoint(
                    observed_at=Instant.from_ms(1_700_086_400_000),
                    equity=Decimal("1100"),
                ),
            ),
        )
        assert r.strategy_name == "vwap_mean_revert"

    def test_rejects_non_positive_initial_equity(self) -> None:
        with pytest.raises(ValidationError, match="initial_equity must be > 0"):
            BacktestReport(
                strategy_name="x",
                period=_tr(),
                initial_equity=Decimal("0"),
                final_equity=Decimal("0"),
                trades=(),
                equity_curve=(),
            )

    def test_rejects_trades_out_of_chronological_order(self) -> None:
        t_late = BacktestTrade(
            opened_at=Instant.from_ms(1_700_000_060_000),
            closed_at=Instant.from_ms(1_700_000_120_000),
            side=TradeSide.LONG,
            entry_price=Decimal("100"),
            exit_price=Decimal("110"),
            size=Decimal("1"),
            pnl=Decimal("10"),
        )
        t_early = BacktestTrade(
            opened_at=Instant.from_ms(1_700_000_000_000),
            closed_at=Instant.from_ms(1_700_000_030_000),
            side=TradeSide.LONG,
            entry_price=Decimal("100"),
            exit_price=Decimal("105"),
            size=Decimal("1"),
            pnl=Decimal("5"),
        )
        with pytest.raises(ValidationError, match="trades must be sorted"):
            BacktestReport(
                strategy_name="x",
                period=_tr(),
                initial_equity=Decimal("1000"),
                final_equity=Decimal("1015"),
                trades=(t_late, t_early),
                equity_curve=(),
            )
