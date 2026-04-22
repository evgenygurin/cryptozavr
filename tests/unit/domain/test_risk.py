"""Risk domain types: TradeIntent / Violation / RiskDecision + enums."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.application.strategy.enums import StrategySide
from cryptozavr.domain.exceptions import ValidationError
from cryptozavr.domain.risk import (
    RiskDecision,
    RiskStatus,
    Severity,
    TradeIntent,
    Violation,
)
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.venues import MarketType, VenueId


def _sample_symbol() -> Symbol:
    return Symbol(
        venue=VenueId.KUCOIN,
        base="BTC",
        quote="USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )


def _sample_intent(**overrides: object) -> TradeIntent:
    defaults: dict[str, object] = {
        "venue": VenueId.KUCOIN,
        "symbol": _sample_symbol(),
        "side": StrategySide.LONG,
        "size": Decimal("100"),
    }
    defaults.update(overrides)
    return TradeIntent(**defaults)  # type: ignore[arg-type]


class TestTradeIntent:
    def test_happy_path_defaults(self) -> None:
        intent = _sample_intent()
        assert intent.venue == VenueId.KUCOIN
        assert intent.symbol.base == "BTC"
        assert intent.side == StrategySide.LONG
        assert intent.size == Decimal("100")
        assert intent.leverage == Decimal(1)
        assert intent.reason == ""
        assert intent.recent_losses == 0
        assert intent.current_balance is None
        assert intent.current_exposure_pct is None
        assert intent.today_pnl_pct is None

    @pytest.mark.parametrize("bad_size", [Decimal("0"), Decimal("-1")])
    def test_size_non_positive_rejected(self, bad_size: Decimal) -> None:
        with pytest.raises(ValidationError, match="size must be > 0"):
            _sample_intent(size=bad_size)

    @pytest.mark.parametrize("bad_leverage", [Decimal("0"), Decimal("0.5")])
    def test_leverage_below_one_rejected(self, bad_leverage: Decimal) -> None:
        with pytest.raises(ValidationError, match="leverage must be >= 1"):
            _sample_intent(leverage=bad_leverage)

    def test_recent_losses_negative_rejected(self) -> None:
        with pytest.raises(ValidationError, match="recent_losses must be >= 0"):
            _sample_intent(recent_losses=-1)

    def test_current_balance_negative_rejected_and_none_allowed(self) -> None:
        with pytest.raises(ValidationError, match="current_balance must be >= 0"):
            _sample_intent(current_balance=Decimal("-1"))
        # None is the documented "caller did not populate" marker.
        intent = _sample_intent(current_balance=None)
        assert intent.current_balance is None

    def test_current_exposure_pct_out_of_range_rejected_boundaries_allowed(self) -> None:
        for bad in (Decimal("-0.01"), Decimal("1.01")):
            with pytest.raises(ValidationError, match=r"current_exposure_pct"):
                _sample_intent(current_exposure_pct=bad)
        # Boundaries are inclusive.
        _sample_intent(current_exposure_pct=Decimal("0"))
        _sample_intent(current_exposure_pct=Decimal("1"))

    def test_today_pnl_pct_none_allowed(self) -> None:
        """None marks 'no PnL data yet' — DailyLossHandler will skip."""
        intent = _sample_intent(today_pnl_pct=None)
        assert intent.today_pnl_pct is None

    @pytest.mark.parametrize(
        "valid_value",
        [
            Decimal("-1"),
            Decimal("-0.5"),
            Decimal("0"),
            Decimal("0.5"),
            Decimal("1"),
        ],
    )
    def test_today_pnl_pct_boundaries_and_inner_values_allowed(
        self,
        valid_value: Decimal,
    ) -> None:
        intent = _sample_intent(today_pnl_pct=valid_value)
        assert intent.today_pnl_pct == valid_value

    @pytest.mark.parametrize("bad", [Decimal("-1.01"), Decimal("1.01")])
    def test_today_pnl_pct_out_of_range_rejected(self, bad: Decimal) -> None:
        with pytest.raises(ValidationError, match=r"today_pnl_pct"):
            _sample_intent(today_pnl_pct=bad)


class TestViolation:
    def test_happy_path_decimal_deny(self) -> None:
        v = Violation(
            handler_name="Exposure",
            policy_field="max_position_pct",
            severity=Severity.DENY,
            message="exposure 32.1% exceeds limit 25.0%",
            observed=Decimal("0.321"),
            limit=Decimal("0.25"),
        )
        assert v.severity == Severity.DENY
        assert v.handler_name == "Exposure"
        assert v.observed == Decimal("0.321")

    def test_happy_path_int_warn(self) -> None:
        v = Violation(
            handler_name="Cooldown",
            policy_field="cooldown_after_n_losses",
            severity=Severity.WARN,
            message="3 recent losses >= cooldown threshold 3",
            observed=3,
            limit=3,
        )
        assert v.severity == Severity.WARN
        assert isinstance(v.observed, int)

    def test_empty_handler_name_or_policy_field_rejected(self) -> None:
        with pytest.raises(ValidationError, match="handler_name must not be empty"):
            Violation(
                handler_name="",
                policy_field="max_leverage",
                severity=Severity.DENY,
                message="msg",
                observed=Decimal("5"),
                limit=Decimal("3"),
            )
        with pytest.raises(ValidationError, match="policy_field must not be empty"):
            Violation(
                handler_name="RiskPolicy",
                policy_field="",
                severity=Severity.DENY,
                message="msg",
                observed=Decimal("5"),
                limit=Decimal("3"),
            )


def _deny_violation() -> Violation:
    return Violation(
        handler_name="RiskPolicy",
        policy_field="max_leverage",
        severity=Severity.DENY,
        message="leverage 10x exceeds max 5x",
        observed=Decimal("10"),
        limit=Decimal("5"),
    )


def _warn_violation() -> Violation:
    return Violation(
        handler_name="Exposure",
        policy_field="max_position_pct",
        severity=Severity.WARN,
        message="exposure 26% slightly above soft cap 25%",
        observed=Decimal("0.26"),
        limit=Decimal("0.25"),
    )


class TestRiskDecision:
    def test_ok_with_empty_violations_valid(self) -> None:
        decision = RiskDecision(
            status=RiskStatus.OK,
            violations=(),
            evaluated_at_ms=1_700_000_000_000,
        )
        assert decision.status == RiskStatus.OK
        assert decision.violations == ()

    def test_ok_with_any_violations_rejected(self) -> None:
        with pytest.raises(ValidationError, match="OK status requires empty violations"):
            RiskDecision(
                status=RiskStatus.OK,
                violations=(_warn_violation(),),
                evaluated_at_ms=1_700_000_000_000,
            )

    def test_warn_with_single_warn_violation_valid(self) -> None:
        decision = RiskDecision(
            status=RiskStatus.WARN,
            violations=(_warn_violation(),),
            evaluated_at_ms=1_700_000_000_000,
        )
        assert decision.status == RiskStatus.WARN
        assert len(decision.violations) == 1

    def test_warn_cannot_contain_deny_severity(self) -> None:
        with pytest.raises(ValidationError, match="WARN status cannot contain DENY"):
            RiskDecision(
                status=RiskStatus.WARN,
                violations=(_deny_violation(),),
                evaluated_at_ms=1_700_000_000_000,
            )

    def test_warn_with_empty_violations_rejected(self) -> None:
        with pytest.raises(ValidationError, match="WARN requires >= 1 violation"):
            RiskDecision(
                status=RiskStatus.WARN,
                violations=(),
                evaluated_at_ms=1_700_000_000_000,
            )

    def test_deny_with_one_deny_violation_valid(self) -> None:
        decision = RiskDecision(
            status=RiskStatus.DENY,
            violations=(_deny_violation(), _warn_violation()),
            evaluated_at_ms=1_700_000_000_000,
        )
        assert decision.status == RiskStatus.DENY
        assert any(v.severity == Severity.DENY for v in decision.violations)

    def test_deny_with_only_warn_rejected(self) -> None:
        with pytest.raises(ValidationError, match="DENY status requires"):
            RiskDecision(
                status=RiskStatus.DENY,
                violations=(_warn_violation(),),
                evaluated_at_ms=1_700_000_000_000,
            )
