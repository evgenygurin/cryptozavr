"""Phase 2D MCP payload DTOs — wire-format mirror of domain StrategySpec.

Domain `StrategySpec` lives in `cryptozavr.application.strategy.strategy_spec`
and uses `Symbol` (frozen dataclass) with `arbitrary_types_allowed=True`.
That means `StrategySpec.model_validate(json_dict)` cannot construct a
Symbol from raw JSON — it expects a pre-built Symbol. The MCP wire surface
therefore needs primitive-typed payload DTOs that expose `to_domain()`
converters. `validate_strategy` (and all other 2D tools) consume these
payloads, not the domain type directly.
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
from cryptozavr.application.strategy.strategy_spec import (
    Condition,
    IndicatorRef,
    StrategyEntry,
    StrategyExit,
    StrategySpec,
)
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.domain.venues import MarketType, VenueId


class SymbolPayload(BaseModel):
    """Wire-format Symbol: primitive fields, not the domain dataclass."""

    model_config = ConfigDict(frozen=True)

    venue: VenueId
    base: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    market_type: MarketType = MarketType.SPOT
    native_symbol: str = Field(min_length=1)

    def to_domain(self) -> Symbol:
        """Construct the domain Symbol. Raises domain.ValidationError on bad input."""
        return Symbol(
            venue=self.venue,
            base=self.base,
            quote=self.quote,
            market_type=self.market_type,
            native_symbol=self.native_symbol,
        )


class IndicatorRefPayload(BaseModel):
    """Wire-format IndicatorRef. Period > 0, source defaults to CLOSE."""

    model_config = ConfigDict(frozen=True)

    kind: IndicatorKind
    period: int = Field(gt=0)
    source: PriceSource = PriceSource.CLOSE

    def to_domain(self) -> IndicatorRef:
        return IndicatorRef(kind=self.kind, period=self.period, source=self.source)


class ConditionPayload(BaseModel):
    """Wire-format Condition. rhs is either another IndicatorRef or a Decimal threshold."""

    model_config = ConfigDict(frozen=True)

    lhs: IndicatorRefPayload
    op: ComparatorOp
    rhs: IndicatorRefPayload | Decimal

    @model_validator(mode="after")
    def _rhs_decimal_is_finite(self) -> ConditionPayload:
        if isinstance(self.rhs, Decimal) and not self.rhs.is_finite():
            raise ValueError("ConditionPayload.rhs Decimal must be finite (got NaN/inf)")
        return self

    def to_domain(self) -> Condition:
        rhs_dom: IndicatorRef | Decimal
        rhs_dom = self.rhs.to_domain() if isinstance(self.rhs, IndicatorRefPayload) else self.rhs
        return Condition(lhs=self.lhs.to_domain(), op=self.op, rhs=rhs_dom)


class StrategyEntryPayload(BaseModel):
    """Wire-format StrategyEntry. At least one condition."""

    model_config = ConfigDict(frozen=True)

    side: StrategySide
    conditions: tuple[ConditionPayload, ...] = Field(min_length=1)

    def to_domain(self) -> StrategyEntry:
        return StrategyEntry(
            side=self.side,
            conditions=tuple(c.to_domain() for c in self.conditions),
        )


class StrategyExitPayload(BaseModel):
    """Wire-format StrategyExit.

    Bail-out invariant (at least one of conditions / take_profit_pct / stop_loss_pct)
    is enforced by the domain StrategyExit model_validator, not here — so the
    payload itself can be partially built before to_domain() is called.
    """

    model_config = ConfigDict(frozen=True)

    conditions: tuple[ConditionPayload, ...] = Field(default=())
    take_profit_pct: Decimal | None = None
    stop_loss_pct: Decimal | None = None

    def to_domain(self) -> StrategyExit:
        return StrategyExit(
            conditions=tuple(c.to_domain() for c in self.conditions),
            take_profit_pct=self.take_profit_pct,
            stop_loss_pct=self.stop_loss_pct,
        )


class StrategySpecPayload(BaseModel):
    """Wire-format StrategySpec.

    Cross-field invariant: top-level `venue` must equal `symbol.venue`. Domain
    StrategySpec relies on this implicitly (same VenueId is duplicated for
    convenience + transport compactness); we enforce it in the payload layer
    so that JSON clients get a clear error instead of silent inconsistency.
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=128)
    description: str = Field(max_length=1024)
    venue: VenueId
    symbol: SymbolPayload
    timeframe: Timeframe
    entry: StrategyEntryPayload
    exit: StrategyExitPayload
    size_pct: Decimal = Field(gt=0, le=1)
    version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _venue_matches_symbol_venue(self) -> StrategySpecPayload:
        if self.venue != self.symbol.venue:
            raise ValueError(
                f"StrategySpecPayload.venue ({self.venue.value!r}) must equal "
                f"symbol.venue ({self.symbol.venue.value!r})",
            )
        return self

    def to_domain(self) -> StrategySpec:
        return StrategySpec(
            name=self.name,
            description=self.description,
            venue=self.venue,
            symbol=self.symbol.to_domain(),
            timeframe=self.timeframe,
            entry=self.entry.to_domain(),
            exit=self.exit.to_domain(),
            size_pct=self.size_pct,
            version=self.version,
        )


# -------------------------- Response DTOs ---------------------------------


class ValidationIssueDTO(BaseModel):
    """Single pydantic-like error, flattened for MCP wire format."""

    model_config = ConfigDict(frozen=True)

    location: list[str | int]
    message: str
    type: str


class ValidateStrategyResponse(BaseModel):
    """Response for validate_strategy tool.

    Coherence invariant: `valid=True` implies `issues` is empty, and
    `valid=False` requires at least one issue. This prevents nonsensical
    responses on the wire.
    """

    model_config = ConfigDict(frozen=True)

    valid: bool
    issues: list[ValidationIssueDTO] = Field(default_factory=list)

    @model_validator(mode="after")
    def _coherence(self) -> ValidateStrategyResponse:
        if self.valid and self.issues:
            raise ValueError("ValidateStrategyResponse: valid=True but issues not empty")
        if not self.valid and not self.issues:
            raise ValueError("ValidateStrategyResponse: valid=False requires at least one issue")
        return self
