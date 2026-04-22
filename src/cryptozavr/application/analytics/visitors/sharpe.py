"""SharpeRatioVisitor: annualised Sharpe = (mean(r) - rf) / stdev(r) * sqrt(k).

Returns `None` when insufficient data prevents computation (fewer than two
points, no usable returns, or zero variance). Callers MUST distinguish
`None` ("no Sharpe available") from `Decimal("0")` ("computed zero Sharpe").

`annualisation_factor` (default 365, i.e. daily equity samples) must match
the cadence of `equity_curve`. For hourly data pass 8760, for 4h pass 2190.
Visitors do not inspect timestamp spacing.
"""

from __future__ import annotations

import itertools
import logging
from decimal import Decimal

from cryptozavr.application.analytics.backtest_report import BacktestReport

_LOG = logging.getLogger(__name__)
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

    def visit(self, report: BacktestReport) -> Decimal | None:
        curve = report.equity_curve
        if len(curve) < _MIN_POINTS_FOR_RETURNS:
            return None
        returns: list[Decimal] = []
        skipped = 0
        for prev, curr in itertools.pairwise(curve):
            if prev.equity == 0:
                skipped += 1
                continue
            returns.append((curr.equity - prev.equity) / prev.equity)
        if skipped:
            _LOG.warning(
                "sharpe: skipped %d zero-equity segments in strategy=%r (possible data gap)",
                skipped,
                report.strategy_name,
            )
        if len(returns) < _MIN_POINTS_FOR_RETURNS:
            return None
        mean = sum(returns, Decimal("0")) / Decimal(len(returns))
        # Sample variance (Bessel's correction) — matches canonical Sharpe
        # literature; `len(returns) >= 2` guaranteed above.
        denominator = Decimal(len(returns) - 1)
        variance = sum(((r - mean) ** 2 for r in returns), Decimal("0")) / denominator
        if variance == 0:
            return None
        stdev = variance.sqrt()
        return (mean - self._rf) / stdev * self._k.sqrt()
