"""RiskEngine orchestration: chain order, aggregation, evaluated_at_ms."""

from __future__ import annotations

import time
from decimal import Decimal

from cryptozavr.application.risk.engine import (
    RiskEngine,
    _aggregate_status,
    default_handler_chain,
)
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
from cryptozavr.domain.risk import (
    RiskStatus,
    Severity,
    TradeIntent,
    Violation,
)
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


def _benign_intent() -> TradeIntent:
    # All handlers pass: leverage=1, exposure=0.1, post-trade=900>=100, losses=0.
    return _sample_intent(
        leverage=Decimal("1"),
        size=Decimal("100"),
        current_balance=Decimal("1000"),
        recent_losses=0,
    )


# --- default_handler_chain --------------------------------------------------


def test_default_handler_chain_returns_canonical_5_in_order() -> None:
    chain = default_handler_chain()
    assert len(chain) == 5
    assert isinstance(chain[0], RiskPolicyHandler)
    assert isinstance(chain[1], ExposureHandler)
    assert isinstance(chain[2], LiquidityHandler)
    assert isinstance(chain[3], CooldownHandler)
    assert isinstance(chain[4], KillSwitchHandler)


# --- end-to-end scenarios ---------------------------------------------------


def test_all_handlers_clear_status_ok() -> None:
    ks = KillSwitch()
    engine = RiskEngine(default_handler_chain(), ks)
    decision = engine.evaluate(_benign_intent(), _valid_policy())
    assert decision.status == RiskStatus.OK
    assert decision.violations == ()


def test_single_warn_violation_status_warn() -> None:
    ks = KillSwitch()
    engine = RiskEngine(default_handler_chain(), ks)
    # Trigger ExposureHandler with WARN severity.
    policy = _valid_policy(
        max_position_pct=LimitDecimal(value=Decimal("0.25"), severity=Severity.WARN),
    )
    intent = _sample_intent(
        size=Decimal("400"),
        current_balance=Decimal("1000"),  # exposure 0.4
    )
    decision = engine.evaluate(intent, policy)
    assert decision.status == RiskStatus.WARN
    assert len(decision.violations) == 1
    assert decision.violations[0].handler_name == "Exposure"


def test_single_deny_violation_status_deny() -> None:
    ks = KillSwitch()
    engine = RiskEngine(default_handler_chain(), ks)
    intent = _sample_intent(leverage=Decimal("100"))  # way above 5 default
    decision = engine.evaluate(intent, _valid_policy())
    assert decision.status == RiskStatus.DENY
    assert any(v.handler_name == "RiskPolicy" for v in decision.violations)


def test_multi_warn_warn_aggregates_to_warn() -> None:
    ks = KillSwitch()
    engine = RiskEngine(default_handler_chain(), ks)
    # Trigger RiskPolicy + Exposure both with WARN severity.
    policy = _valid_policy(
        max_leverage=LimitDecimal(value=Decimal("5"), severity=Severity.WARN),
        max_position_pct=LimitDecimal(value=Decimal("0.25"), severity=Severity.WARN),
    )
    intent = _sample_intent(
        leverage=Decimal("10"),
        size=Decimal("400"),
        current_balance=Decimal("1000"),
    )
    decision = engine.evaluate(intent, policy)
    assert decision.status == RiskStatus.WARN
    assert len(decision.violations) == 2


def test_warn_plus_deny_aggregates_to_deny() -> None:
    ks = KillSwitch()
    engine = RiskEngine(default_handler_chain(), ks)
    policy = _valid_policy(
        max_leverage=LimitDecimal(value=Decimal("5"), severity=Severity.WARN),
        # Exposure stays DENY (default)
    )
    intent = _sample_intent(
        leverage=Decimal("10"),  # WARN violation
        size=Decimal("400"),
        current_balance=Decimal("1000"),  # exposure 0.4 > 0.25 → DENY
    )
    decision = engine.evaluate(intent, policy)
    assert decision.status == RiskStatus.DENY
    assert len(decision.violations) == 2


def test_kill_switch_overrides_even_when_all_limits_pass() -> None:
    ks = KillSwitch()
    ks.engage(reason="emergency halt")
    engine = RiskEngine(default_handler_chain(), ks)
    decision = engine.evaluate(_benign_intent(), _valid_policy())
    assert decision.status == RiskStatus.DENY
    assert any(v.handler_name == "KillSwitch" for v in decision.violations)


# --- _aggregate_status pure-function table ----------------------------------


def _viol(severity: Severity) -> Violation:
    return Violation(
        handler_name="X",
        policy_field="y",
        severity=severity,
        message="m",
        observed=Decimal("1"),
        limit=Decimal("0"),
    )


def test_aggregate_empty_is_ok() -> None:
    assert _aggregate_status([]) == RiskStatus.OK


def test_aggregate_single_deny_is_deny() -> None:
    assert _aggregate_status([_viol(Severity.DENY)]) == RiskStatus.DENY


def test_aggregate_two_warns_is_warn() -> None:
    assert _aggregate_status([_viol(Severity.WARN), _viol(Severity.WARN)]) == RiskStatus.WARN


def test_aggregate_warn_plus_deny_is_deny() -> None:
    # Mixed severities resolve to DENY regardless of order — any DENY wins.
    assert _aggregate_status([_viol(Severity.WARN), _viol(Severity.DENY)]) == RiskStatus.DENY
    assert _aggregate_status([_viol(Severity.DENY), _viol(Severity.WARN)]) == RiskStatus.DENY


# --- evaluated_at_ms + type invariants --------------------------------------


def test_evaluated_at_ms_is_plausible_millisecond_value() -> None:
    engine = RiskEngine(default_handler_chain(), KillSwitch())
    before = int(time.time() * 1000)
    decision = engine.evaluate(_benign_intent(), _valid_policy())
    after = int(time.time() * 1000)
    # Allow 5000 ms slop for CI jitter.
    assert before - 5000 <= decision.evaluated_at_ms <= after + 5000


def test_handlers_stored_as_tuple_not_mutable_list() -> None:
    chain = [RiskPolicyHandler(), ExposureHandler()]
    engine = RiskEngine(chain, KillSwitch())
    # Access private storage (tested intent: immutability of chain).
    assert isinstance(engine._handlers, tuple)
