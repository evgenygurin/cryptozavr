"""Pydantic DSL for RiskPolicy — 5 limits with per-limit severity config."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cryptozavr.domain.risk import Severity


class LimitDecimal(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: Decimal = Field(gt=0)
    severity: Severity = Severity.DENY


class LimitInt(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: int = Field(gt=0)
    severity: Severity = Severity.DENY


class RiskPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_leverage: LimitDecimal
    max_position_pct: LimitDecimal
    max_daily_loss_pct: LimitDecimal
    cooldown_after_n_losses: LimitInt
    min_balance_buffer: LimitDecimal

    @model_validator(mode="after")
    def _bounds(self) -> RiskPolicy:
        for name in ("max_position_pct", "max_daily_loss_pct"):
            lim: LimitDecimal = getattr(self, name)
            if lim.value > 1:
                raise ValueError(
                    f"RiskPolicy.{name}.value must be in (0, 1] (got {lim.value})",
                )
        if self.max_leverage.value < 1:
            raise ValueError(
                "RiskPolicy.max_leverage.value must be >= 1 (sub-1x caps are nonsense)",
            )
        return self
