"""TotalReturnVisitor: (final - initial) / initial."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.analytics.visitors.total_return import TotalReturnVisitor
from tests.unit.application.analytics.fixtures import make_report


def test_ten_percent_gain() -> None:
    report = make_report(equity_curve=("1000", "1050", "1100"))
    assert TotalReturnVisitor().visit(report) == Decimal("0.1")


def test_twenty_percent_loss() -> None:
    report = make_report(equity_curve=("1000", "900", "800"))
    assert TotalReturnVisitor().visit(report) == Decimal("-0.2")


def test_zero_return_when_final_equals_initial() -> None:
    report = make_report(equity_curve=("1000", "1000", "1000"))
    assert TotalReturnVisitor().visit(report) == Decimal("0")


def test_visitor_has_stable_name() -> None:
    assert TotalReturnVisitor().name == "total_return"
