"""Pydantic DTOs for StrategySpec DSL.

All models are frozen (immutability) and ship validators as `model_validator`
methods so round-trips through `.model_dump()` / `.model_validate()` are
safe. Field-level ranges use `Field(gt=..., le=...)` to surface the bound
in the schema for future MCP tool introspection.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from cryptozavr.application.strategy.enums import IndicatorKind, PriceSource


class IndicatorRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: IndicatorKind
    period: int = Field(gt=0, le=500)
    source: PriceSource = PriceSource.CLOSE
