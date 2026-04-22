"""Pydantic DTOs for StrategySpec DSL.

All models are frozen (immutability) and ship validators as `model_validator`
methods so round-trips through `.model_dump()` / `.model_validate()` are
safe. Field-level ranges use `Field(gt=..., le=...)` to surface the bound
in the schema for future MCP tool introspection.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cryptozavr.application.strategy.enums import (
    ComparatorOp,
    IndicatorKind,
    PriceSource,
)


class IndicatorRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: IndicatorKind
    period: int = Field(gt=0, le=500)
    source: PriceSource = PriceSource.CLOSE


class Condition(BaseModel):
    model_config = ConfigDict(frozen=True)

    lhs: IndicatorRef
    op: ComparatorOp
    rhs: IndicatorRef | Decimal

    @model_validator(mode="after")
    def _rhs_is_finite_if_decimal(self) -> Condition:
        if isinstance(self.rhs, Decimal) and not self.rhs.is_finite():
            raise ValueError("Condition.rhs Decimal must be finite (got NaN/inf)")
        return self
