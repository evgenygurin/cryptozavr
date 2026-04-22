"""SharpeRatioVisitor: annualised Sharpe = (mean(r) - rf) / stdev(r) * sqrt(k)."""

from __future__ import annotations

import itertools
from decimal import Decimal

from cryptozavr.application.analytics.backtest_report import BacktestReport

_DEFAULT_ANNUALISATION = Decimal("365")
_MIN_POINTS_FOR_RETURNS = 2


class SharpeRatioVisitor:
    name = "sharpe_ratio"

    def __init__(
        self,
        *,
        risk_free_rate: Decimal = Decimal("0"),
        annualisation_factor: Decimal = _DEFAULT_ANNUALISATION,
    ) -> None:
        self._rf = risk_free_rate
        self._k = annualisation_factor

    def visit(self, report: BacktestReport) -> Decimal:
        curve = report.equity_curve
        if len(curve) < _MIN_POINTS_FOR_RETURNS:
            return Decimal("0")
        returns: list[Decimal] = []
        for prev, curr in itertools.pairwise(curve):
            if prev.equity == 0:
                continue
            returns.append((curr.equity - prev.equity) / prev.equity)
        if not returns:
            return Decimal("0")
        mean = sum(returns, Decimal("0")) / Decimal(len(returns))
        variance = sum(((r - mean) ** 2 for r in returns), Decimal("0")) / Decimal(len(returns))
        if variance == 0:
            return Decimal("0")
        stdev = variance.sqrt()
        return (mean - self._rf) / stdev * self._k.sqrt()
