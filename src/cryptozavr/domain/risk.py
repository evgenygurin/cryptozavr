"""Risk-layer domain types: TradeIntent / Violation / RiskDecision + enums."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from cryptozavr.application.strategy.enums import StrategySide
from cryptozavr.domain.exceptions import ValidationError
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.venues import VenueId


class RiskStatus(StrEnum):
    """Verdict of RiskEngine.evaluate()."""

    OK = "ok"
    WARN = "warn"
    DENY = "deny"


class Severity(StrEnum):
    """Per-limit config knob AND per-violation tag."""

    WARN = "warn"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class TradeIntent:
    """Neutral trade request. Backtest emits it; live will too (later)."""

    venue: VenueId
    symbol: Symbol
    side: StrategySide
    size: Decimal
    leverage: Decimal = Decimal(1)
    reason: str = ""
    recent_losses: int = 0
    current_balance: Decimal | None = None
    current_exposure_pct: Decimal | None = None

    def __post_init__(self) -> None:
        if self.size <= 0:
            raise ValidationError("TradeIntent.size must be > 0")
        if self.leverage < 1:
            raise ValidationError("TradeIntent.leverage must be >= 1 (no sub-1x)")
        if self.recent_losses < 0:
            raise ValidationError("TradeIntent.recent_losses must be >= 0")
        if self.current_balance is not None and self.current_balance < 0:
            raise ValidationError("TradeIntent.current_balance must be >= 0 when set")
        if self.current_exposure_pct is not None and (
            self.current_exposure_pct < 0 or self.current_exposure_pct > 1
        ):
            raise ValidationError(
                "TradeIntent.current_exposure_pct must be in [0, 1] when set",
            )


@dataclass(frozen=True, slots=True)
class Violation:
    """Atomic policy-limit breach discovered by a handler."""

    handler_name: str
    policy_field: str
    severity: Severity
    message: str
    observed: Decimal | int
    limit: Decimal | int

    def __post_init__(self) -> None:
        if not self.handler_name:
            raise ValidationError("Violation.handler_name must not be empty")
        if not self.policy_field:
            raise ValidationError("Violation.policy_field must not be empty")


@dataclass(frozen=True, slots=True)
class RiskDecision:
    """Aggregate verdict + structured violation list."""

    status: RiskStatus
    violations: tuple[Violation, ...]
    evaluated_at_ms: int

    def __post_init__(self) -> None:
        if self.status == RiskStatus.OK and self.violations:
            raise ValidationError("RiskDecision: OK status requires empty violations")
        has_deny = any(v.severity == Severity.DENY for v in self.violations)
        if self.status == RiskStatus.DENY and not has_deny:
            raise ValidationError(
                "RiskDecision: DENY status requires >= 1 DENY-severity violation",
            )
        if self.status == RiskStatus.WARN:
            if not self.violations:
                raise ValidationError("RiskDecision: WARN requires >= 1 violation")
            if has_deny:
                raise ValidationError(
                    "RiskDecision: WARN status cannot contain DENY-severity violations",
                )
