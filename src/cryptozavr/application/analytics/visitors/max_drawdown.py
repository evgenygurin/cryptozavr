"""MaxDrawdownVisitor: max ((peak - equity) / peak) across equity_curve."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.analytics.backtest_report import BacktestReport


class MaxDrawdownVisitor:
    name = "max_drawdown"

    def visit(self, report: BacktestReport) -> Decimal:
        peak = Decimal("0")
        max_dd = Decimal("0")
        for point in report.equity_curve:
            peak = max(peak, point.equity)
            if peak > 0:
                dd = (peak - point.equity) / peak
                max_dd = max(max_dd, dd)
        return max_dd
