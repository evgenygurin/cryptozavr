"""WinRateVisitor: sum(pnl > 0) / len(trades)."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.analytics.visitors.win_rate import WinRateVisitor
from tests.unit.application.analytics.fixtures import _trade, make_report


def test_half_winners() -> None:
    trades = (_trade(0, "10"), _trade(1, "-5"), _trade(2, "8"), _trade(3, "-3"))
    report = make_report(trades=trades)
    assert WinRateVisitor().visit(report) == Decimal("0.5")


def test_all_winners() -> None:
    trades = (_trade(0, "10"), _trade(1, "5"))
    report = make_report(trades=trades)
    assert WinRateVisitor().visit(report) == Decimal("1")


def test_all_losers() -> None:
    trades = (_trade(0, "-10"), _trade(1, "-5"))
    report = make_report(trades=trades)
    assert WinRateVisitor().visit(report) == Decimal("0")


def test_empty_trades_returns_zero() -> None:
    report = make_report(trades=())
    assert WinRateVisitor().visit(report) == Decimal("0")


def test_zero_pnl_trade_is_not_a_win() -> None:
    trades = (_trade(0, "0"), _trade(1, "10"))
    report = make_report(trades=trades)
    assert WinRateVisitor().visit(report) == Decimal("0.5")


def test_visitor_name() -> None:
    assert WinRateVisitor().name == "win_rate"
