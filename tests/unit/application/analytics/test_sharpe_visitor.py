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


def test_constant_equity_returns_none() -> None:
    """Zero variance ⇒ Sharpe undefined; visitor returns None so callers
    can distinguish 'no variance' from 'Sharpe happens to be zero'."""
    report = _report(("1000", "1000", "1000", "1000"))
    assert SharpeRatioVisitor().visit(report) is None


def test_fewer_than_two_points_returns_none() -> None:
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
    assert SharpeRatioVisitor().visit(bare) is None


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
    assert a is not None
    assert b is not None
    ratio = b / a
    assert Decimal("1.99") < ratio < Decimal("2.01")


def test_risk_free_rate_shifts_numerator_downward() -> None:
    """With rf > 0, Sharpe drops because we subtract rf from each return's mean.
    Confirms `risk_free_rate` lands in the numerator, not the denominator."""
    report = _report(("1000", "1010", "1020.1", "1030.3", "1040.6"))
    zero_rf = SharpeRatioVisitor(risk_free_rate=Decimal("0")).visit(report)
    pos_rf = SharpeRatioVisitor(risk_free_rate=Decimal("0.005")).visit(report)
    assert zero_rf is not None
    assert pos_rf is not None
    assert pos_rf < zero_rf


def test_rf_equal_to_mean_gives_sharpe_zero() -> None:
    """If risk_free_rate exactly equals the mean return, numerator collapses
    to zero — a direct algebraic check on the formula. The curve needs
    non-zero variance to avoid the variance==0 short-circuit, so we use
    alternating returns (0%, +2%) whose mean is 1%."""
    # e0=1000, e1=1000 (r1=0), e2=1020 (r2=0.02). Mean return = 0.01.
    report = _report(("1000", "1000", "1020"))
    result = SharpeRatioVisitor(
        risk_free_rate=Decimal("0.01"),
        annualisation_factor=Decimal("1"),
    ).visit(report)
    # Floating-round tolerance — Decimal(sqrt) can introduce tiny residuals.
    assert result is not None
    assert abs(result) < Decimal("1e-20")


def test_ground_truth_two_return_series() -> None:
    """Hand-computed Sharpe against the formula
      mean = (0.10 + (-0.05)) / 2 = 0.025
      sample_var = ((0.10 - 0.025)^2 + (-0.05 - 0.025)^2) / (2-1) = 0.01125
      stdev = sqrt(0.01125) ≈ 0.1060660...
      sharpe (k=1) = 0.025 / 0.1060660... ≈ 0.2357022...
    Pins the implementation to the canonical definition; catches regressions
    in mean/variance math or wrong variance denominator."""
    # Build curve such that r1=+0.10, r2=-0.05.
    # e0=1000 → e1=1100 (+10%), then e2=1100*0.95=1045 (-5%).
    report = _report(("1000", "1100", "1045"))
    result = SharpeRatioVisitor(annualisation_factor=Decimal("1")).visit(report)
    assert result is not None
    expected = Decimal("0.2357022603955158")
    # Relative tolerance: 1e-10 is well inside Decimal's default precision
    # and far tighter than any reasonable implementation drift.
    assert abs(result - expected) < Decimal("1e-10")


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
def test_property_sharpe_finite_or_none_for_bounded_curves(
    values: list[Decimal],
) -> None:
    """Sharpe is either a finite Decimal or None (on zero-variance curves).
    Never NaN/inf and never raises."""
    report = _report(tuple(str(v) for v in values))
    result = SharpeRatioVisitor().visit(report)
    assert result is None or result.is_finite()
