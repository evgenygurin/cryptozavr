"""5 RiskHandler implementations — happy / violation / skip paths."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.risk.handlers import (
    CooldownHandler,
    ExposureHandler,
    KillSwitchHandler,
    LiquidityHandler,
    RiskPolicyHandler,
)
from cryptozavr.application.risk.kill_switch import KillSwitch
from cryptozavr.application.risk.risk_policy import (
    LimitDecimal,
    LimitInt,
    RiskPolicy,
)
from cryptozavr.application.strategy.enums import StrategySide
from cryptozavr.domain.risk import Severity, TradeIntent
from cryptozavr.domain.symbols import MarketType, Symbol
from cryptozavr.domain.venues import VenueId

# --- builders ---------------------------------------------------------------


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


def _valid_policy(**overrides: object) -> RiskPolicy:
    defaults: dict[str, object] = {
        "max_leverage": LimitDecimal(value=Decimal("5")),
        "max_position_pct": LimitDecimal(value=Decimal("0.25")),
        "max_daily_loss_pct": LimitDecimal(value=Decimal("0.05")),
        "cooldown_after_n_losses": LimitInt(value=3),
        "min_balance_buffer": LimitDecimal(value=Decimal("100")),
    }
    defaults.update(overrides)
    return RiskPolicy(**defaults)  # type: ignore[arg-type]


# --- RiskPolicyHandler (max_leverage) ---------------------------------------


class TestRiskPolicyHandler:
    def test_no_violation_at_leverage_equal_to_limit(self) -> None:
        h = RiskPolicyHandler()
        intent = _sample_intent(leverage=Decimal("5"))
        policy = _valid_policy(max_leverage=LimitDecimal(value=Decimal("5")))
        assert h.evaluate(intent, policy, KillSwitch()) is None

    def test_violation_above_limit_default_severity_deny(self) -> None:
        h = RiskPolicyHandler()
        intent = _sample_intent(leverage=Decimal("10"))
        policy = _valid_policy(max_leverage=LimitDecimal(value=Decimal("5")))
        v = h.evaluate(intent, policy, KillSwitch())
        assert v is not None
        assert v.severity == Severity.DENY
        assert v.handler_name == "RiskPolicy"
        assert v.policy_field == "max_leverage"
        assert v.observed == Decimal("10")
        assert v.limit == Decimal("5")

    def test_violation_preserves_custom_warn_severity(self) -> None:
        h = RiskPolicyHandler()
        intent = _sample_intent(leverage=Decimal("10"))
        policy = _valid_policy(
            max_leverage=LimitDecimal(value=Decimal("5"), severity=Severity.WARN),
        )
        v = h.evaluate(intent, policy, KillSwitch())
        assert v is not None
        assert v.severity == Severity.WARN


# --- ExposureHandler (max_position_pct) -------------------------------------


class TestExposureHandler:
    def test_skip_when_current_balance_is_none(self) -> None:
        h = ExposureHandler()
        intent = _sample_intent(current_balance=None, size=Decimal("10_000_000"))
        assert h.evaluate(intent, _valid_policy(), KillSwitch()) is None

    def test_skip_when_current_balance_is_zero(self) -> None:
        """Zero-balance edge is handled by LiquidityHandler; Exposure skips."""
        h = ExposureHandler()
        intent = _sample_intent(current_balance=Decimal("0"), size=Decimal("10"))
        assert h.evaluate(intent, _valid_policy(), KillSwitch()) is None

    def test_no_violation_when_exposure_within_limit(self) -> None:
        h = ExposureHandler()
        # exposure = 100 / 1000 = 0.10 <= 0.25
        intent = _sample_intent(size=Decimal("100"), current_balance=Decimal("1000"))
        assert h.evaluate(intent, _valid_policy(), KillSwitch()) is None

    def test_violation_when_exposure_exceeds_limit(self) -> None:
        h = ExposureHandler()
        # exposure = 400 / 1000 = 0.40 > 0.25
        intent = _sample_intent(size=Decimal("400"), current_balance=Decimal("1000"))
        v = h.evaluate(intent, _valid_policy(), KillSwitch())
        assert v is not None
        assert v.severity == Severity.DENY
        assert v.handler_name == "Exposure"
        assert v.policy_field == "max_position_pct"
        assert v.limit == Decimal("0.25")
        assert v.observed == Decimal("0.4000")


# --- LiquidityHandler (min_balance_buffer) ----------------------------------


class TestLiquidityHandler:
    def test_skip_when_current_balance_is_none(self) -> None:
        h = LiquidityHandler()
        intent = _sample_intent(current_balance=None, size=Decimal("10"))
        assert h.evaluate(intent, _valid_policy(), KillSwitch()) is None

    def test_no_violation_when_post_trade_balance_meets_buffer(self) -> None:
        h = LiquidityHandler()
        # post = 500 - 100 = 400 >= 100
        intent = _sample_intent(size=Decimal("100"), current_balance=Decimal("500"))
        assert h.evaluate(intent, _valid_policy(), KillSwitch()) is None

    def test_violation_when_post_trade_balance_drops_below_buffer(self) -> None:
        h = LiquidityHandler()
        # post = 150 - 100 = 50 < 100
        intent = _sample_intent(size=Decimal("100"), current_balance=Decimal("150"))
        v = h.evaluate(intent, _valid_policy(), KillSwitch())
        assert v is not None
        assert v.severity == Severity.DENY
        assert v.handler_name == "Liquidity"
        assert v.policy_field == "min_balance_buffer"
        assert v.observed == Decimal("50")
        assert v.limit == Decimal("100")


# --- CooldownHandler (recent_losses) ----------------------------------------


class TestCooldownHandler:
    def test_no_violation_below_threshold(self) -> None:
        h = CooldownHandler()
        intent = _sample_intent(recent_losses=2)
        policy = _valid_policy(cooldown_after_n_losses=LimitInt(value=3))
        assert h.evaluate(intent, policy, KillSwitch()) is None

    def test_violation_at_threshold_inclusive(self) -> None:
        h = CooldownHandler()
        intent = _sample_intent(recent_losses=3)
        policy = _valid_policy(cooldown_after_n_losses=LimitInt(value=3))
        v = h.evaluate(intent, policy, KillSwitch())
        assert v is not None
        assert v.severity == Severity.DENY
        assert v.handler_name == "Cooldown"
        assert v.policy_field == "cooldown_after_n_losses"
        assert v.observed == 3
        assert v.limit == 3

    def test_violation_above_threshold(self) -> None:
        h = CooldownHandler()
        intent = _sample_intent(recent_losses=10)
        policy = _valid_policy(cooldown_after_n_losses=LimitInt(value=3))
        v = h.evaluate(intent, policy, KillSwitch())
        assert v is not None
        assert v.observed == 10


# --- KillSwitchHandler ------------------------------------------------------


class TestKillSwitchHandler:
    def test_no_violation_when_disengaged(self) -> None:
        h = KillSwitchHandler()
        assert h.evaluate(_sample_intent(), _valid_policy(), KillSwitch()) is None

    def test_violation_when_engaged(self) -> None:
        h = KillSwitchHandler()
        ks = KillSwitch()
        ks.engage(reason="panic")
        v = h.evaluate(_sample_intent(), _valid_policy(), ks)
        assert v is not None
        assert v.severity == Severity.DENY
        assert v.handler_name == "KillSwitch"
        assert v.policy_field == "kill_switch"
        assert "panic" in v.message
        assert v.observed == 1
        assert v.limit == 0

    def test_violation_is_deny_even_if_policy_other_limits_use_warn(self) -> None:
        """KillSwitch severity is non-negotiable; independent of policy config."""
        h = KillSwitchHandler()
        ks = KillSwitch()
        ks.engage(reason="non-negotiable")
        policy = _valid_policy(
            # Other limits set to WARN — must not downgrade the kill switch.
            max_leverage=LimitDecimal(value=Decimal("5"), severity=Severity.WARN),
            max_position_pct=LimitDecimal(value=Decimal("0.25"), severity=Severity.WARN),
        )
        v = h.evaluate(_sample_intent(), policy, ks)
        assert v is not None
        assert v.severity == Severity.DENY
