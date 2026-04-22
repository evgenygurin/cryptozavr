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
    StrategySide,
)
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.domain.venues import VenueId


class IndicatorRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: IndicatorKind
    # `period > 0` — no upper bound beyond Python int range. Canonical
    # long-lookback indicators (200-day SMA, 365-day MA) sit above any
    # round-number cap we might pick, and the DSL isn't the right layer
    # to guess venue-specific warm-up limits.
    period: int = Field(gt=0)
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


class StrategyEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    side: StrategySide
    # ALL conditions must hold (AND). Phase 2A keeps the MVP gate simple —
    # OR-of-ANDs DSL is a 2A+1 extension via a wrapper type. No upper
    # bound: strategies may legitimately AND many filters (regime +
    # volume + trend + momentum + volatility + session-time); picking
    # an arbitrary cap just creates a surprise ValidationError later.
    conditions: tuple[Condition, ...] = Field(min_length=1)


class StrategyExit(BaseModel):
    model_config = ConfigDict(frozen=True)

    # Any condition triggers exit (OR). Exit is looser than entry because
    # risk management has more bail-out paths than entry has setups. No
    # upper bound for the same reason as StrategyEntry.
    conditions: tuple[Condition, ...] = Field(default=())
    take_profit_pct: Decimal | None = None
    stop_loss_pct: Decimal | None = None

    @model_validator(mode="after")
    def _has_bail_out_and_positive_thresholds(self) -> StrategyExit:
        has_any = (
            bool(self.conditions)
            or self.take_profit_pct is not None
            or self.stop_loss_pct is not None
        )
        if not has_any:
            raise ValueError(
                "StrategyExit: provide at least one of conditions / "
                "take_profit_pct / stop_loss_pct",
            )
        if self.take_profit_pct is not None and self.take_profit_pct <= 0:
            raise ValueError(
                f"StrategyExit.take_profit_pct must be > 0 (got {self.take_profit_pct!r})"
            )
        if self.stop_loss_pct is not None and self.stop_loss_pct <= 0:
            raise ValueError(f"StrategyExit.stop_loss_pct must be > 0 (got {self.stop_loss_pct!r})")
        return self


class StrategySpec(BaseModel):
    # `arbitrary_types_allowed` because Symbol is a frozen dataclass, not a
    # Pydantic model. Pydantic validates it by isinstance check only.
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    name: str = Field(min_length=1, max_length=128)
    description: str = Field(max_length=1024)
    venue: VenueId
    symbol: Symbol
    timeframe: Timeframe
    entry: StrategyEntry
    exit: StrategyExit
    size_pct: Decimal = Field(gt=0, le=1)
    version: int = Field(default=1, ge=1)
