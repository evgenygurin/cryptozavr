"""SharpeRatioVisitor: annualised (mean - rf) / stdev."""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from cryptozavr.application.analytics.backtest_report import (
    BacktestReport,
    EquityPoint,
)
from cryptozavr.application.analytics.visitors.sharpe import SharpeRatioVisitor
from cryptozavr.domain.value_objects import Instant, TimeRange


def _curve(values: tuple[str, ...]) -> tuple[EquityPoint, ...]:
    return tuple(
        EquityPoint(
            observed_at=Instant.from_ms(1_700_000_000_000 + i * 86_400_000),
            equity=Decimal(v),
        )
        for i, v in enumerate(values)
    )


def _report(values: tuple[str, ...]) -> BacktestReport:
    curve = _curve(values)
    return BacktestReport(
        strategy_name="x",
        period=TimeRange(start=curve[0].observed_at, end=curve[-1].observed_at),
        initial_equity=Decimal(values[0]),
        final_equity=Decimal(values[-1]),
        trades=(),
        equity_curve=curve,
    )


def test_constant_equity_has_zero_sharpe() -> None:
    report = _report(("1000", "1000", "1000", "1000"))
    assert SharpeRatioVisitor().visit(report) == Decimal("0")


def test_fewer_than_two_points_returns_zero() -> None:
    bare = BacktestReport(
        strategy_name="x",
        period=TimeRange(
            start=Instant.from_ms(1_700_000_000_000),
            end=Instant.from_ms(1_700_000_060_000),
        ),
        initial_equity=Decimal("1000"),
        final_equity=Decimal("1000"),
        trades=(),
        equity_curve=(
            EquityPoint(
                observed_at=Instant.from_ms(1_700_000_000_000),
                equity=Decimal("1000"),
            ),
        ),
    )
    assert SharpeRatioVisitor().visit(bare) == Decimal("0")


def test_positive_sharpe_for_steady_growth() -> None:
    report = _report(("1000", "1010", "1020.1", "1030.3", "1040.6"))
    result = SharpeRatioVisitor().visit(report)
    assert result > Decimal("0")


def test_name_default() -> None:
    assert SharpeRatioVisitor().name == "sharpe_ratio"


def test_annualisation_factor_scales_linearly_by_sqrt() -> None:
    report = _report(("1000", "1010", "1020.1", "1030.3", "1040.6"))
    a = SharpeRatioVisitor(annualisation_factor=Decimal("365")).visit(report)
    b = SharpeRatioVisitor(annualisation_factor=Decimal("1460")).visit(report)
    ratio = b / a
    assert Decimal("1.99") < ratio < Decimal("2.01")


@given(
    st.lists(
        st.decimals(
            min_value="900",
            max_value="1100",
            allow_nan=False,
            allow_infinity=False,
            places=2,
        ),
        min_size=5,
        max_size=30,
    )
)
def test_property_sharpe_finite_for_bounded_curves(values: list[Decimal]) -> None:
    report = _report(tuple(str(v) for v in values))
    result = SharpeRatioVisitor().visit(report)
    assert result.is_finite()
