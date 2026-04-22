# Phase 2A — StrategySpec DSL + Builder (design)

> **Status:** LOCKED on 2026-04-22. Ralph-loop directive "cначала C, потом A.
> Все как положенно делай" + silent-consent on the "defaults" option
> collapsed the open questions to their first-option choices (see
> "Locked decisions" below). Phase 2C is merged (PR #2 → main).

## Goal

Ship a declarative, Pydantic-validated strategy description (`StrategySpec`)
plus a fluent builder (`StrategySpecBuilder`) that future Phase 2B backtest
execution and Phase 2D MCP tools can consume. No execution, no persistence,
no MCP surface in this sub-project — those are 2B/2D/2E.

## Non-goals

- **No `BacktestEngine`.** That's 2B. A `StrategySpec` is a pure DTO here;
  executing it is a future consumer's concern.
- **No MCP tools.** The `validate_strategy` / `save_strategy` /
  `list_strategies` tools live in 2D on top of 2A+2E.
- **No persistence.** `strategy_specs` table + pgvector embedding land in 2E.
  For 2A the spec is an in-memory Pydantic model.
- **No `StrategySpec` cloning (Prototype pattern).** The spec enables it via
  `model_copy(update=...)` but we don't add explicit preset-loading here.

## Architecture

```text
src/cryptozavr/application/strategy/
├── __init__.py
├── strategy_spec.py           # StrategySpec, StrategyEntry, StrategyExit
├── enums.py                   # StrategySide, IndicatorKind, ComparatorOp
└── builder.py                 # StrategySpecBuilder (fluent)
```

Tests mirror the layout at `tests/unit/application/strategy/`.

## Data model (proposal — `strategy_spec.py`)

```python
from pydantic import BaseModel, Field, model_validator
from decimal import Decimal

from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.venues import VenueId

class IndicatorRef(BaseModel, frozen=True):
    """References a technical indicator by name + parameters.
    Phase 2A does not compute indicators — consumers (2B BacktestEngine,
    later live-signal engine in phase 4) resolve the name to a concrete
    implementation. We validate structure only."""

    kind: IndicatorKind                # e.g. SMA, EMA, RSI, ATR
    period: int = Field(gt=0, le=500)  # bar count
    source: PriceSource = PriceSource.CLOSE  # open/high/low/close/hlc3

class Condition(BaseModel, frozen=True):
    """Left-hand-side indicator compared against a right-hand-side
    (either another indicator, a constant price, or a constant scalar)."""

    lhs: IndicatorRef
    op: ComparatorOp  # GT / GTE / LT / LTE / CROSSES_ABOVE / CROSSES_BELOW
    rhs: IndicatorRef | Decimal

class StrategyEntry(BaseModel, frozen=True):
    side: StrategySide  # LONG / SHORT
    # ALL conditions must hold (AND). Phase 2A keeps the MVP gate simple —
    # OR-of-ANDs DSL is a 2A+1 extension.
    conditions: tuple[Condition, ...] = Field(min_length=1, max_length=8)

class StrategyExit(BaseModel, frozen=True):
    # Any condition triggers exit (OR). Exit is looser than entry because
    # risk management has more bail-out paths than entry has setups.
    conditions: tuple[Condition, ...] = Field(min_length=1, max_length=8)
    take_profit_pct: Decimal | None = None  # e.g. 0.05 = +5%
    stop_loss_pct: Decimal | None = None

class StrategySpec(BaseModel, frozen=True):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(max_length=1024)
    venue: VenueId
    symbol: Symbol
    timeframe: Timeframe  # 1m / 5m / 15m / 1h / 4h / 1d (reuse domain enum)
    entry: StrategyEntry
    exit: StrategyExit
    size_pct: Decimal = Field(gt=0, le=1)  # fraction of equity per trade
    version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _cross_validate(self) -> "StrategySpec":
        # e.g. stop_loss must be less aggressive than take_profit's sign,
        # size_pct <= 1, timeframe compatible with conditions' indicator
        # periods (e.g. 500-period SMA on 1m timeframe ≈ 8h warm-up).
        return self
```

Key invariants enforced on construction (via `model_validator`):

- Entry and exit conditions are non-empty.
- `size_pct` in `(0, 1]`.
- `take_profit_pct` / `stop_loss_pct` positive when present.
- At least one of `take_profit_pct`, `stop_loss_pct`, or exit conditions
  is set (a strategy must have *some* way to close positions).
- Symbol / venue consistency (venue must list the symbol as supported —
  checked via existing `SymbolRegistry`).

## Builder pattern (proposal — `builder.py`)

```python
class StrategySpecBuilder:
    """Fluent step-by-step construction of a StrategySpec. Each `with_*`
    returns a new builder (immutable under the hood) so partially-built
    specs can be shared without aliasing bugs."""

    def __init__(self) -> None: ...

    def with_name(self, name: str) -> "StrategySpecBuilder": ...
    def with_market(
        self,
        *,
        venue: VenueId,
        symbol: Symbol,
        timeframe: Timeframe,
    ) -> "StrategySpecBuilder": ...
    def with_entry(
        self,
        *,
        side: StrategySide,
        conditions: Iterable[Condition],
    ) -> "StrategySpecBuilder": ...
    def with_exit(
        self,
        *,
        conditions: Iterable[Condition] = (),
        take_profit_pct: Decimal | None = None,
        stop_loss_pct: Decimal | None = None,
    ) -> "StrategySpecBuilder": ...
    def with_size_pct(self, pct: Decimal) -> "StrategySpecBuilder": ...

    def build(self) -> StrategySpec:
        """Final construction — triggers full Pydantic validation.
        Raises ValidationError if any required piece is missing."""
```

Rationale for Builder vs direct constructor:

- A `StrategySpec` has 8+ fields, half of which are nested structures.
  Direct construction is noisy in tests; Builder is ergonomic.
- Future MCP tools in 2D (`start_strategy` with elicitations) map naturally
  onto builder steps — one `with_*` per elicitation turn.
- Immutable intermediate state lets presets / templates be shared without
  the "oh no, the template got mutated" bug.

## Test plan (target ≥ 40 unit tests)

**`StrategySpec` (happy + invariants)** — ~15 tests
- Happy path: full valid spec round-trips through `.model_dump()`.
- Each invariant has a dedicated failing-case test
  (empty conditions, size_pct=0/1.5, negative take_profit, etc.).
- Property test: `hypothesis.strategies.builds` generator never produces
  a spec that fails validation on a second `.model_validate()` — idempotent.

**`StrategySpecBuilder`** — ~15 tests
- Builds valid spec in the order user specifies.
- Missing required field → `ValidationError` at `.build()`.
- Builder is immutable — `b1 = builder.with_name("x"); b2 = b1.with_name("y")`
  leaves `b1` unchanged.
- Builder round-trips against direct-constructor output for the same inputs.

**`Condition` / `IndicatorRef` / `StrategyEntry` / `StrategyExit`** — ~10 tests
- Reject out-of-range indicator periods.
- Reject unknown `IndicatorKind` / `ComparatorOp` (Pydantic handles enum
  validation but we assert the error surface is stable for MCP callers).

## Interface contract for 2B / 2C / 2D (future)

- **2B `BacktestEngine`** consumes `StrategySpec`, resolves `IndicatorKind`
  to a compute function, generates a `BacktestReport` (defined in 2C).
- **2C `BacktestAnalyticsService`** (already shipped) consumes the report.
  No 2C change in 2A.
- **2D MCP tools** (`validate_strategy`, `save_strategy`,
  `list_strategies`, `compare_strategies`) construct or retrieve
  `StrategySpec` instances and wire them through 2B + 2C.

## Patterns touched

- **Builder** (#16 in the shipped patterns list) — new in Phase 2A.
- **Prototype** (#20) — implicit via `model_copy(update=...)` on the frozen
  Pydantic model. No separate `clone()` method.
- **Strategy** (already shipped) — `StrategySpec` is DATA fed to a future
  Strategy-family executor; no new subtypes here.

## Acceptance for 2A

- All modules listed under Architecture exist and pass type-checks.
- ≥ 40 unit tests covering happy path + invariants + property tests for
  idempotent validation.
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src`
  all pass.
- No regressions — total suite stays green.
- Short entry in `CHANGELOG.md` under `[Unreleased]` describing 2A.

## Locked decisions

1. **`IndicatorKind` enum** — 2A ships with `SMA`, `EMA`, `RSI`, `MACD`,
   `ATR`, `VOLUME`. `BBANDS` and `ADX` deferred to 2A+1 (adding an enum
   member is a non-breaking additive change later).
2. **`Timeframe`** — reuse `cryptozavr.domain.value_objects.Timeframe`
   (already has `M1/M5/M15/M30/H1/H4/D1/W1` + `to_milliseconds()`).
   One enum for the whole system; strategy-scoped clone is a smell.
3. **Position sizing** — `size_pct: Decimal` in `(0, 1]` (fraction of
   equity). Quote-currency sizing lives in Phase 3's `RiskPolicy` where
   it belongs; 2A stays portable across symbols.
4. **Entry conditions** — single AND-gate for 2A. OR-of-ANDs is a
   non-breaking additive change later (new `AnyOf` wrapper type).
5. **Cloning** — rely on Pydantic's `model_copy(update={...})`. No
   explicit `Builder.from_spec`; add only if a 2D MCP tool actually
   needs it (YAGNI for 2A).
6. **Timeframe-vs-period mismatch** — **deferred**. The initially
   proposed "warn if warm-up > 7 days" heuristic contradicts itself:
   a 200-day SMA on daily candles (200 days of warm-up) is the
   canonical long-trend filter and shouldn't warn, yet would trip the
   7-day bound. Without a principled line between "legit long lookback"
   and "config typo", 2A ships no warm-up warning. Revisit in 2A+1 when
   real user feedback tells us what "weird" actually looks like.

Ready to proceed to `superpowers:writing-plans`.
