"""RiskEngine — sync, stateless orchestrator over the handler chain."""

from __future__ import annotations

import time
from collections.abc import Sequence

from cryptozavr.application.risk.handlers import (
    CooldownHandler,
    DailyLossHandler,
    ExposureHandler,
    KillSwitchHandler,
    LiquidityHandler,
    RiskHandler,
    RiskPolicyHandler,
)
from cryptozavr.application.risk.kill_switch import KillSwitch
from cryptozavr.application.risk.risk_policy import RiskPolicy
from cryptozavr.domain.risk import (
    RiskDecision,
    RiskStatus,
    Severity,
    TradeIntent,
    Violation,
)


def default_handler_chain() -> tuple[RiskHandler, ...]:
    """Canonical order per MVP spec.

    RiskPolicy → Exposure → Liquidity → DailyLoss → Cooldown → KillSwitch.
    """
    return (
        RiskPolicyHandler(),
        ExposureHandler(),
        LiquidityHandler(),
        DailyLossHandler(),
        CooldownHandler(),
        KillSwitchHandler(),
    )


def _aggregate_status(violations: Sequence[Violation]) -> RiskStatus:
    if any(v.severity == Severity.DENY for v in violations):
        return RiskStatus.DENY
    if violations:
        return RiskStatus.WARN
    return RiskStatus.OK


class RiskEngine:
    """Runs handlers in order; aggregates violations into a RiskDecision."""

    def __init__(
        self,
        handlers: Sequence[RiskHandler],
        kill_switch: KillSwitch,
    ) -> None:
        self._handlers: tuple[RiskHandler, ...] = tuple(handlers)
        self._kill_switch = kill_switch

    def evaluate(
        self,
        intent: TradeIntent,
        policy: RiskPolicy,
    ) -> RiskDecision:
        violations: list[Violation] = []
        for handler in self._handlers:
            v = handler.evaluate(intent, policy, self._kill_switch)
            if v is not None:
                violations.append(v)
        return RiskDecision(
            status=_aggregate_status(violations),
            violations=tuple(violations),
            evaluated_at_ms=int(time.time() * 1000),
        )
