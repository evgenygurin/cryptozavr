"""ProfitFactorVisitor: gross_profit / |gross_loss|.

Returns:
- `None` when no trades were recorded (nothing to divide) — "N/A".
- `None` when gross loss is zero but there are trades — "ratio undefined"
  (all-winning or all-flat portfolio). Callers that need to distinguish
  "no loss despite trading" from "no trades at all" can check
  `len(report.trades)` alongside the visitor result.
- `Decimal("0")` when gross profit is zero and gross loss is positive
  (all-losing portfolio).
"""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.analytics.backtest_report import BacktestReport


class ProfitFactorVisitor:
    name = "profit_factor"

    def visit(self, report: BacktestReport) -> Decimal | None:
        if not report.trades:
            return None
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
