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
from typing import Any

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


# -------------------------- Unit 2D-2 DTOs --------------------------------
# Added by read-only tools (list / explain / diff). Kept in the same module
# as the payload DTOs because consumers (strategy_read_only.py tool module
# + tests) naturally import them together; splitting would just add an
# import layer without reducing coupling.


class StoredStrategySummaryDTO(BaseModel):
    """Summary of a persisted strategy (no embedded spec — fetch separately).

    Shape locked now so 2E can swap the in-memory stub for a real repository
    without changing the wire contract.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    version: int
    created_at_ms: int


class ListStrategiesResponse(BaseModel):
    """Response for list_strategies. Until 2E lands persistence this returns
    an empty list and sets `note` to explain the stub. Coherent once the
    repository is wired: `note` becomes None for a healthy response.
    """

    model_config = ConfigDict(frozen=True)

    strategies: list[StoredStrategySummaryDTO] = Field(default_factory=list)
    note: str | None = None


class ExplanationSectionDTO(BaseModel):
    """One titled section of the explain_strategy output (plain-text body)."""

    model_config = ConfigDict(frozen=True)

    title: str
    body: str


class ExplainStrategyResponse(BaseModel):
    """Response for explain_strategy.

    Coherence invariants:
      * `error` set → no `markdown` / `sections` (don't produce garbage on bad input).
      * `error` None → `markdown` required (success must carry content).
    """

    model_config = ConfigDict(frozen=True)

    markdown: str | None = None
    sections: list[ExplanationSectionDTO] = Field(default_factory=list)
    error: str | None = None

    @model_validator(mode="after")
    def _coherence(self) -> ExplainStrategyResponse:
        if self.error is not None and (self.markdown is not None or self.sections):
            raise ValueError("ExplainStrategyResponse: error set but content present")
        if self.error is None and self.markdown is None:
            raise ValueError("ExplainStrategyResponse: success path requires markdown")
        return self


class FieldDiffDTO(BaseModel):
    """A single leaf-level difference between two strategy specs.

    `path` is a JSON-pointer-like string rooted at the top-level spec
    (e.g. "/name", "/entry/conditions/0/lhs/period"). `left` / `right`
    hold the raw values from `model_dump()` output — typed `Any` because
    they can be str / int / bool / None / Decimal-as-str depending on the
    field.
    """

    model_config = ConfigDict(frozen=True)

    path: str
    left: Any | None = None
    right: Any | None = None


class DiffStrategiesResponse(BaseModel):
    """Response for diff_strategies.

    Coherence invariants:
      * `errors` set → `equal=False` and `differences=[]` (can't compare what
        didn't parse).
      * No errors + `equal=True` → `differences=[]` (tautology).
    """

    model_config = ConfigDict(frozen=True)

    equal: bool
    differences: list[FieldDiffDTO] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _coherence(self) -> DiffStrategiesResponse:
        if self.errors and (self.equal or self.differences):
            raise ValueError("DiffStrategiesResponse: errors set but equal/differences produced")
        if not self.errors and self.equal and self.differences:
            raise ValueError("DiffStrategiesResponse: equal=True but differences not empty")
        return self
