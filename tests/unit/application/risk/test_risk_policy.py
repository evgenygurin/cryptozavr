"""RiskPolicy DSL: per-limit bounds + severity config."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError as PydanticValidationError

from cryptozavr.application.risk.risk_policy import (
    LimitDecimal,
    LimitInt,
    RiskPolicy,
)
from cryptozavr.domain.risk import Severity


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


def test_happy_path_defaults_deny_severity() -> None:
    policy = _valid_policy()
    assert policy.max_leverage.value == Decimal("5")
    assert policy.max_leverage.severity == Severity.DENY
    assert policy.max_position_pct.severity == Severity.DENY
    assert policy.cooldown_after_n_losses.value == 3
    assert policy.cooldown_after_n_losses.severity == Severity.DENY


def test_custom_severity_warn_accepted() -> None:
    policy = _valid_policy(
        max_position_pct=LimitDecimal(value=Decimal("0.25"), severity=Severity.WARN),
    )
    assert policy.max_position_pct.severity == Severity.WARN


def test_limit_decimal_value_zero_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        LimitDecimal(value=Decimal("0"))


def test_limit_int_value_zero_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        LimitInt(value=0)


def test_max_position_pct_above_one_rejected() -> None:
    with pytest.raises(PydanticValidationError, match="max_position_pct"):
        _valid_policy(max_position_pct=LimitDecimal(value=Decimal("1.5")))


def test_max_daily_loss_pct_above_one_rejected() -> None:
    with pytest.raises(PydanticValidationError, match="max_daily_loss_pct"):
        _valid_policy(max_daily_loss_pct=LimitDecimal(value=Decimal("1.5")))


def test_max_leverage_below_one_rejected() -> None:
    with pytest.raises(PydanticValidationError, match="max_leverage"):
        _valid_policy(max_leverage=LimitDecimal(value=Decimal("0.5")))


def test_max_position_pct_equals_one_valid() -> None:
    policy = _valid_policy(max_position_pct=LimitDecimal(value=Decimal("1")))
    assert policy.max_position_pct.value == Decimal("1")
