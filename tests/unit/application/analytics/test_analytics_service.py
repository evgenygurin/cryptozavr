"""BacktestAnalyticsService runs every registered visitor against a report."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.application.analytics.analytics_service import (
    BacktestAnalyticsService,
)
from cryptozavr.application.analytics.visitors.total_return import TotalReturnVisitor
from cryptozavr.application.analytics.visitors.win_rate import WinRateVisitor
from tests.unit.application.analytics.fixtures import _trade, make_report


def test_run_all_returns_one_result_per_visitor() -> None:
    service = BacktestAnalyticsService([TotalReturnVisitor(), WinRateVisitor()])
    report = make_report(
        initial="1000",
        final="1100",
        trades=(_trade(0, "10"), _trade(1, "-5")),
    )
    results = service.run_all(report)
    assert results == {"total_return": Decimal("0.1"), "win_rate": Decimal("0.5")}


def test_run_all_preserves_visitor_order() -> None:
    visitors = [TotalReturnVisitor(), WinRateVisitor()]
    service = BacktestAnalyticsService(visitors)
    report = make_report(trades=(_trade(0, "1"),))
    assert list(service.run_all(report).keys()) == ["total_return", "win_rate"]


def test_run_all_rejects_duplicate_visitor_names() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        BacktestAnalyticsService([TotalReturnVisitor(), TotalReturnVisitor()])


def test_run_all_propagates_visitor_exception() -> None:
    class _Boom:
        name = "boom"

        def visit(self, report):  # type: ignore[no-untyped-def]
            raise RuntimeError("boom")

    service = BacktestAnalyticsService([_Boom()])
    report = make_report()
    with pytest.raises(RuntimeError, match="boom"):
        service.run_all(report)
