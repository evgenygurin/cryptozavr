"""TotalReturnVisitor: (final_equity - initial_equity) / initial_equity."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.analytics.backtest_report import BacktestReport


class TotalReturnVisitor:
    name = "total_return"

    def visit(self, report: BacktestReport) -> Decimal:
        return (report.final_equity - report.initial_equity) / report.initial_equity
