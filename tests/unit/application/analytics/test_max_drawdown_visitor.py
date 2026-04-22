"""MaxDrawdownVisitor: max (peak - equity) / peak across the equity curve."""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from cryptozavr.application.analytics.backtest_report import (
    BacktestReport,
    EquityPoint,
)
from cryptozavr.application.analytics.visitors.max_drawdown import (
    MaxDrawdownVisitor,
)
from cryptozavr.domain.value_objects import Instant, TimeRange
from tests.unit.application.analytics.fixtures import make_report


def test_simple_drawdown() -> None:
    report = make_report(equity_curve=("1000", "1200", "900", "1100"))
    assert MaxDrawdownVisitor().visit(report) == Decimal("0.25")


def test_monotone_increasing_has_zero_drawdown() -> None:
    report = make_report(equity_curve=("1000", "1100", "1200", "1500"))
    assert MaxDrawdownVisitor().visit(report) == Decimal("0")


def test_total_loss_returns_one() -> None:
    report = make_report(equity_curve=("1000", "500", "0"))
    assert MaxDrawdownVisitor().visit(report) == Decimal("1")


def test_empty_curve_returns_zero() -> None:
    bare = BacktestReport(
        strategy_name="x",
        period=TimeRange(
            start=Instant.from_ms(1_700_000_000_000),
            end=Instant.from_ms(1_700_000_060_000),
        ),
        initial_equity=Decimal("1000"),
        final_equity=Decimal("1000"),
        trades=(),
        equity_curve=(),
    )
    assert MaxDrawdownVisitor().visit(bare) == Decimal("0")


def test_name() -> None:
    assert MaxDrawdownVisitor().name == "max_drawdown"


@given(
    st.lists(
        st.decimals(min_value="1", max_value="1000000", allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=50,
    ).map(lambda xs: sorted(xs))
)
def test_property_monotone_increasing_curve_has_zero_drawdown(
    values: list[Decimal],
) -> None:
    curve = tuple(
        EquityPoint(observed_at=Instant.from_ms(1_700_000_000_000 + i * 60_000), equity=v)
        for i, v in enumerate(values)
    )
    report = BacktestReport(
        strategy_name="x",
        period=TimeRange(
            start=Instant.from_ms(1_700_000_000_000),
            end=Instant.from_ms(1_700_000_000_000 + len(values) * 60_000),
        ),
        initial_equity=values[0],
        final_equity=values[-1],
        trades=(),
        equity_curve=curve,
    )
    assert MaxDrawdownVisitor().visit(report) == Decimal("0")


@given(
    st.lists(
        st.decimals(min_value="1", max_value="1000000", allow_nan=False, allow_infinity=False),
        min_size=2,
        max_size=50,
    )
)
def test_property_drawdown_is_in_zero_one(values: list[Decimal]) -> None:
    curve = tuple(
        EquityPoint(observed_at=Instant.from_ms(1_700_000_000_000 + i * 60_000), equity=v)
        for i, v in enumerate(values)
    )
    report = BacktestReport(
        strategy_name="x",
        period=TimeRange(
            start=Instant.from_ms(1_700_000_000_000),
            end=Instant.from_ms(1_700_000_000_000 + len(values) * 60_000),
        ),
        initial_equity=values[0],
        final_equity=values[-1],
        trades=(),
        equity_curve=curve,
    )
    dd = MaxDrawdownVisitor().visit(report)
    assert Decimal("0") <= dd <= Decimal("1")
