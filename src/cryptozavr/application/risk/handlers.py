"""Chain-of-Responsibility handlers: 5 concrete checks + RiskHandler Protocol.

Each handler returns ``Violation | None``. Handlers that require caller-
populated context fields (``current_balance``) skip silently when those
fields are ``None`` — documented rationale: a backtest at the first bar has
no balance yet and must not flag every first-bar intent as a violation.
"""

from __future__ import annotations

from decimal import Decimal
from typing import ClassVar, Protocol

from cryptozavr.application.risk.kill_switch import KillSwitch
from cryptozavr.application.risk.risk_policy import RiskPolicy
from cryptozavr.domain.risk import Severity, TradeIntent, Violation


class RiskHandler(Protocol):
    name: ClassVar[str]

    def evaluate(
        self,
        intent: TradeIntent,
        policy: RiskPolicy,
        kill_switch: KillSwitch,
    ) -> Violation | None: ...


class RiskPolicyHandler:
    name: ClassVar[str] = "RiskPolicy"

    def evaluate(
        self,
        intent: TradeIntent,
        policy: RiskPolicy,
        kill_switch: KillSwitch,
    ) -> Violation | None:
        limit = policy.max_leverage
        if intent.leverage > limit.value:
            return Violation(
                handler_name=self.name,
                policy_field="max_leverage",
                severity=limit.severity,
                message=(f"leverage {intent.leverage} exceeds max_leverage {limit.value}"),
                observed=intent.leverage,
                limit=limit.value,
            )
        return None


class ExposureHandler:
    name: ClassVar[str] = "Exposure"

    def evaluate(
        self,
        intent: TradeIntent,
        policy: RiskPolicy,
        kill_switch: KillSwitch,
    ) -> Violation | None:
        if intent.current_balance is None:
            return None
        if intent.current_balance <= 0:
            # Avoid div-by-zero; LiquidityHandler covers zero-balance case.
            return None
        exposure = intent.size / intent.current_balance
        limit = policy.max_position_pct
        if exposure > limit.value:
            return Violation(
                handler_name=self.name,
                policy_field="max_position_pct",
                severity=limit.severity,
                message=(f"exposure {exposure:.4f} exceeds max_position_pct {limit.value}"),
                observed=exposure.quantize(Decimal("0.0001")),
                limit=limit.value,
            )
        return None


class LiquidityHandler:
    name: ClassVar[str] = "Liquidity"

    def evaluate(
        self,
        intent: TradeIntent,
        policy: RiskPolicy,
        kill_switch: KillSwitch,
    ) -> Violation | None:
        if intent.current_balance is None:
            return None
        post_trade_balance = intent.current_balance - intent.size
        limit = policy.min_balance_buffer
        if post_trade_balance < limit.value:
            return Violation(
                handler_name=self.name,
                policy_field="min_balance_buffer",
                severity=limit.severity,
                message=(
                    f"post-trade balance {post_trade_balance} would dip "
                    f"below min_balance_buffer {limit.value}"
                ),
                observed=post_trade_balance,
                limit=limit.value,
            )
        return None


class CooldownHandler:
    name: ClassVar[str] = "Cooldown"

    def evaluate(
        self,
        intent: TradeIntent,
        policy: RiskPolicy,
        kill_switch: KillSwitch,
    ) -> Violation | None:
        limit = policy.cooldown_after_n_losses
        if intent.recent_losses >= limit.value:
            return Violation(
                handler_name=self.name,
                policy_field="cooldown_after_n_losses",
                severity=limit.severity,
                message=(
                    f"recent_losses {intent.recent_losses} triggers cooldown "
                    f"(threshold {limit.value})"
                ),
                observed=intent.recent_losses,
                limit=limit.value,
            )
        return None


class KillSwitchHandler:
    name: ClassVar[str] = "KillSwitch"

    def evaluate(
        self,
        intent: TradeIntent,
        policy: RiskPolicy,
        kill_switch: KillSwitch,
    ) -> Violation | None:
        status = kill_switch.status()
        if not status.engaged:
            return None
        return Violation(
            handler_name=self.name,
            policy_field="kill_switch",
            severity=Severity.DENY,  # non-negotiable; ignores policy severity
            message=f"kill switch engaged: {status.reason}",
            observed=1,  # synthetic "1 = engaged"
            limit=0,
        )
