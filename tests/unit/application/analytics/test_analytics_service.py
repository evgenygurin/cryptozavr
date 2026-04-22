"""BacktestAnalyticsService runs every registered visitor against a report."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.application.analytics.analytics_service import (
    BacktestAnalyticsService,
)
from cryptozavr.application.analytics.visitors.max_drawdown import MaxDrawdownVisitor
from cryptozavr.application.analytics.visitors.profit_factor import ProfitFactorVisitor
from cryptozavr.application.analytics.visitors.sharpe import SharpeRatioVisitor
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


def test_run_all_composes_all_five_visitors_including_none() -> None:
    """End-to-end: all 5 built-in visitors against a realistic report, with
    deliberately all-winning trades so ProfitFactor returns None.
    Confirms:
    - Service tolerates None alongside Decimal values in the result dict
    - Ordering is preserved (insertion order of visitors)
    - Each visitor sees the SAME report (no accidental filtering/rebuilding)
    """
    service = BacktestAnalyticsService(
        [
            TotalReturnVisitor(),
            WinRateVisitor(),
            MaxDrawdownVisitor(),
            ProfitFactorVisitor(),
            SharpeRatioVisitor(),
        ]
    )
    # All trades positive ⇒ gross_loss=0 ⇒ ProfitFactor is None.
    # Equity curve has a peak-to-trough dip so MaxDrawdown > 0, and enough
    # variance that Sharpe doesn't short-circuit.
    report = make_report(
        equity_curve=("1000", "1100", "900", "1050", "1200"),
        trades=(_trade(0, "50"), _trade(1, "75"), _trade(2, "10")),
    )
    results = service.run_all(report)

    assert list(results.keys()) == [
        "total_return",
        "win_rate",
        "max_drawdown",
        "profit_factor",
        "sharpe_ratio",
    ]
    assert results["total_return"] == Decimal("0.2")
    assert results["win_rate"] == Decimal("1")
    # Peak=1100, trough=900 ⇒ drawdown = (1100-900)/1100 = 0.1818...
    max_dd = results["max_drawdown"]
    assert max_dd is not None
    assert Decimal("0.18") < max_dd < Decimal("0.19")
    # All-winning portfolio ⇒ ProfitFactor semantically undefined.
    assert results["profit_factor"] is None
    # Sharpe is a concrete Decimal — curve has non-constant returns.
    assert results["sharpe_ratio"] is not None
