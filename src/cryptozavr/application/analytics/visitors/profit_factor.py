"""ProfitFactorVisitor: gross_profit / |gross_loss|."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.analytics.backtest_report import BacktestReport


class ProfitFactorVisitor:
    name = "profit_factor"

    def visit(self, report: BacktestReport) -> Decimal | None:
        gross_profit = Decimal("0")
        gross_loss = Decimal("0")
        for t in report.trades:
            if t.pnl > 0:
                gross_profit += t.pnl
            elif t.pnl < 0:
                gross_loss += -t.pnl
        if gross_loss == 0:
            return None
        return gross_profit / gross_loss
