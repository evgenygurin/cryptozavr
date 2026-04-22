"""MaxDrawdownVisitor: max ((peak - equity) / peak) across equity_curve.

Returns `Decimal` in `[0, 1]` for a non-empty equity curve; returns `None`
when the curve is empty so callers can distinguish "no drawdown observed"
from "no data to observe".
"""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.analytics.backtest_report import BacktestReport


class MaxDrawdownVisitor:
    name = "max_drawdown"

    def visit(self, report: BacktestReport) -> Decimal | None:
        if not report.equity_curve:
            return None
        peak = Decimal("0")
        max_dd = Decimal("0")
        for point in report.equity_curve:
            peak = max(peak, point.equity)
            if peak > 0:
                dd = (peak - point.equity) / peak
                max_dd = max(max_dd, dd)
        # Defensive clamp — EquityPoint currently validates finite-only, not
        # non-negative; negative equity would mathematically push dd past 1.
        if max_dd > Decimal("1"):
            return Decimal("1")
        return max_dd
