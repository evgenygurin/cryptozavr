"""BacktestAnalyticsService composer — runs a list of Visitor instances."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from cryptozavr.application.analytics.backtest_report import BacktestReport
from cryptozavr.application.analytics.visitors.base import BacktestVisitor


class BacktestAnalyticsService:
    """Runs a list of BacktestVisitor instances against a report.

    Visitor ordering is preserved in the result dict. Visitor exceptions
    propagate — we do not silently swallow metric failures.
    """

    def __init__(self, visitors: Sequence[BacktestVisitor[Any]]) -> None:
        seen: set[str] = set()
        for v in visitors:
            if v.name in seen:
                raise ValueError(f"duplicate visitor name: {v.name!r}")
            seen.add(v.name)
        self._visitors = tuple(visitors)

    def run_all(self, report: BacktestReport) -> dict[str, Any]:
        return {v.name: v.visit(report) for v in self._visitors}
