"""ProfitFactorVisitor: gross_profit / |gross_loss|, None if no losses."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.analytics.visitors.profit_factor import (
    ProfitFactorVisitor,
)
from tests.unit.application.analytics.fixtures import _trade, make_report


def test_two_to_one_ratio() -> None:
    trades = (_trade(0, "15"), _trade(1, "-10"), _trade(2, "5"))
    report = make_report(trades=trades)
    assert ProfitFactorVisitor().visit(report) == Decimal("2")


def test_all_winners_returns_none() -> None:
    trades = (_trade(0, "10"), _trade(1, "5"))
    report = make_report(trades=trades)
    assert ProfitFactorVisitor().visit(report) is None


def test_all_losers_returns_zero() -> None:
    trades = (_trade(0, "-10"), _trade(1, "-5"))
    report = make_report(trades=trades)
    assert ProfitFactorVisitor().visit(report) == Decimal("0")


def test_empty_returns_none() -> None:
    report = make_report(trades=())
    assert ProfitFactorVisitor().visit(report) is None


def test_name() -> None:
    assert ProfitFactorVisitor().name == "profit_factor"
