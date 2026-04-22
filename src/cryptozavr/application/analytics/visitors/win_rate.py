"""WinRateVisitor: proportion of trades with positive pnl."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.analytics.backtest_report import BacktestReport


class WinRateVisitor:
    name = "win_rate"

    def visit(self, report: BacktestReport) -> Decimal:
        if not report.trades:
            return Decimal("0")
        winners = sum(1 for t in report.trades if t.pnl > 0)
        return Decimal(winners) / Decimal(len(report.trades))
