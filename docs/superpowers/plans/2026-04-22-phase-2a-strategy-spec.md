# Phase 2A — StrategySpec DSL + Builder — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax
> for tracking.

**Goal:** Ship `cryptozavr.application.strategy` — a frozen Pydantic
`StrategySpec` DTO plus a fluent, immutable `StrategySpecBuilder` — as a
standalone analytics-independent building block for future 2B backtest
execution and 2D MCP tools.

**Architecture:** Pydantic v2 frozen models with `model_validator` invariants;
reuse existing `domain.value_objects.Timeframe`, `domain.venues.VenueId`,
`domain.symbols.Symbol`. Builder returns a new instance per step (immutable
intermediate state). TDD red→green→refactor per task, small commits.

**Tech Stack:** Python 3.12, Pydantic v2, `hypothesis` for property tests,
`pytest`, `ruff`, `mypy`.

---

## File Structure

```text
src/cryptozavr/application/strategy/
├── __init__.py
├── enums.py            # StrategySide, IndicatorKind, ComparatorOp, PriceSource
├── strategy_spec.py    # IndicatorRef, Condition, StrategyEntry, StrategyExit, StrategySpec
└── builder.py          # StrategySpecBuilder

tests/unit/application/strategy/
├── __init__.py
├── fixtures.py                   # valid_spec() helper
├── test_enums.py
├── test_indicator_ref.py
├── test_condition.py
├── test_strategy_entry.py
├── test_strategy_exit.py
├── test_strategy_spec.py
└── test_builder.py
```

One test module per DTO keeps failure locality tight; the fixtures module
is the single source of "a valid minimal spec" across tests.

## Task Sequence

### Task 1: enums module (`enums.py`)

**Files:**
- Create: `src/cryptozavr/application/strategy/__init__.py`
- Create: `src/cryptozavr/application/strategy/enums.py`
- Create: `tests/unit/application/strategy/__init__.py`
- Test: `tests/unit/application/strategy/test_enums.py`

- [ ] **Step 1: Write failing enum tests**

```python
# tests/unit/application/strategy/test_enums.py
"""Strategy-layer enums: string values are stable across releases (wire
contract for future 2D MCP tools and 2E Supabase persistence)."""

from __future__ import annotations

from cryptozavr.application.strategy.enums import (
    ComparatorOp,
    IndicatorKind,
    PriceSource,
    StrategySide,
)

def test_strategy_side_values() -> None:
    assert StrategySide.LONG.value == "long"
    assert StrategySide.SHORT.value == "short"

def test_indicator_kind_mvp_members() -> None:
    names = {k.name for k in IndicatorKind}
    assert names == {"SMA", "EMA", "RSI", "MACD", "ATR", "VOLUME"}

def test_indicator_kind_values_are_lowercase() -> None:
    for k in IndicatorKind:
        assert k.value == k.name.lower()

def test_comparator_op_includes_crossings() -> None:
    names = {op.name for op in ComparatorOp}
    assert {"GT", "GTE", "LT", "LTE", "CROSSES_ABOVE", "CROSSES_BELOW"} <= names

def test_price_source_defaults_to_close() -> None:
    assert PriceSource.CLOSE.value == "close"
    assert {s.name for s in PriceSource} >= {"OPEN", "HIGH", "LOW", "CLOSE", "HLC3"}
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/application/strategy/test_enums.py -v`
Expected: FAIL with `ModuleNotFoundError: cryptozavr.application.strategy.enums`

- [ ] **Step 3: Implement enums**

```python
# src/cryptozavr/application/strategy/__init__.py
"""Phase 2A: declarative strategy specification DSL + Builder."""
```

```python
# src/cryptozavr/application/strategy/enums.py
"""Strategy-layer enums. Values are the wire contract across MCP + Supabase;
names never change, values are lowercase-snake for JSON cleanliness."""

from __future__ import annotations

from enum import StrEnum

class StrategySide(StrEnum):
    LONG = "long"
    SHORT = "short"

class IndicatorKind(StrEnum):
    SMA = "sma"
    EMA = "ema"
    RSI = "rsi"
    MACD = "macd"
    ATR = "atr"
    VOLUME = "volume"

class ComparatorOp(StrEnum):
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    CROSSES_ABOVE = "crosses_above"
    CROSSES_BELOW = "crosses_below"

class PriceSource(StrEnum):
    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"
    HLC3 = "hlc3"
```

- [ ] **Step 4: Run to verify green**

Run: `uv run pytest tests/unit/application/strategy/test_enums.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/cryptozavr/application/strategy/__init__.py src/cryptozavr/application/strategy/enums.py tests/unit/application/strategy/__init__.py tests/unit/application/strategy/test_enums.py
git commit -F /tmp/commit-msg.txt
```

Commit message (write to /tmp/commit-msg.txt first):
```bash
feat(strategy): enums for 2A (side, indicator, comparator, price source)

Wire contract for future 2D MCP tools and 2E Supabase persistence.
Values are lowercase snake-case for JSON cleanliness; names stay stable.
```

---

### Task 2: IndicatorRef DTO

**Files:**
- Create: `src/cryptozavr/application/strategy/strategy_spec.py`
- Test: `tests/unit/application/strategy/test_indicator_ref.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/application/strategy/test_indicator_ref.py
"""IndicatorRef: kind + period + price source, structurally validated."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cryptozavr.application.strategy.enums import IndicatorKind, PriceSource
from cryptozavr.application.strategy.strategy_spec import IndicatorRef

def test_minimal_indicator_ref_defaults_to_close_source() -> None:
    ref = IndicatorRef(kind=IndicatorKind.SMA, period=20)
    assert ref.source is PriceSource.CLOSE

def test_explicit_source_overrides_default() -> None:
    ref = IndicatorRef(kind=IndicatorKind.EMA, period=12, source=PriceSource.HLC3)
    assert ref.source is PriceSource.HLC3

@pytest.mark.parametrize("period", [0, -1, 501])
def test_period_out_of_range_raises(period: int) -> None:
    with pytest.raises(ValidationError):
        IndicatorRef(kind=IndicatorKind.RSI, period=period)

def test_frozen_cannot_mutate() -> None:
    ref = IndicatorRef(kind=IndicatorKind.SMA, period=20)
    with pytest.raises(ValidationError):
        ref.period = 50  # type: ignore[misc]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/application/strategy/test_indicator_ref.py -v`
Expected: FAIL with `ImportError` on `IndicatorRef`.

- [ ] **Step 3: Implement IndicatorRef**

```python
# src/cryptozavr/application/strategy/strategy_spec.py
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
```

- [ ] **Step 4: Verify green**

Run: `uv run pytest tests/unit/application/strategy/test_indicator_ref.py -v`
Expected: 5 passed (3 parametrized + 2 others).

- [ ] **Step 5: Commit**

```text
feat(strategy): IndicatorRef DTO (frozen, period 1..500)
```

---

### Task 3: Condition DTO

**Files:**
- Modify: `src/cryptozavr/application/strategy/strategy_spec.py`
- Test: `tests/unit/application/strategy/test_condition.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/application/strategy/test_condition.py
"""Condition: lhs indicator op {indicator|decimal constant}."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from cryptozavr.application.strategy.enums import (
    ComparatorOp,
    IndicatorKind,
)
from cryptozavr.application.strategy.strategy_spec import Condition, IndicatorRef

def _ind(kind: IndicatorKind = IndicatorKind.SMA, period: int = 20) -> IndicatorRef:
    return IndicatorRef(kind=kind, period=period)

def test_condition_with_two_indicators() -> None:
    c = Condition(lhs=_ind(IndicatorKind.EMA, 12), op=ComparatorOp.GT, rhs=_ind(IndicatorKind.EMA, 26))
    assert c.op is ComparatorOp.GT
    assert isinstance(c.rhs, IndicatorRef)

def test_condition_with_decimal_constant() -> None:
    c = Condition(lhs=_ind(IndicatorKind.RSI, 14), op=ComparatorOp.LT, rhs=Decimal("30"))
    assert c.rhs == Decimal("30")

def test_condition_rejects_nan_rhs() -> None:
    with pytest.raises(ValidationError):
        Condition(lhs=_ind(), op=ComparatorOp.GT, rhs=Decimal("NaN"))

def test_condition_is_frozen() -> None:
    c = Condition(lhs=_ind(), op=ComparatorOp.GT, rhs=Decimal("100"))
    with pytest.raises(ValidationError):
        c.op = ComparatorOp.LT  # type: ignore[misc]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/application/strategy/test_condition.py -v`
Expected: FAIL with `ImportError` on `Condition`.

- [ ] **Step 3: Implement Condition**

Add to `strategy_spec.py` (imports: `from decimal import Decimal` at top,
`from cryptozavr.application.strategy.enums import ComparatorOp` extend existing import,
new class below `IndicatorRef`):

```python
# Append near top-level imports
from decimal import Decimal
# Extend enum import to include ComparatorOp

class Condition(BaseModel):
    model_config = ConfigDict(frozen=True)

    lhs: IndicatorRef
    op: ComparatorOp
    rhs: IndicatorRef | Decimal

    @model_validator(mode="after")
    def _rhs_is_finite_if_decimal(self) -> "Condition":
        if isinstance(self.rhs, Decimal) and not self.rhs.is_finite():
            raise ValueError("Condition.rhs Decimal must be finite (got NaN/inf)")
        return self
```

Also add `from pydantic import model_validator` to imports.

- [ ] **Step 4: Verify green**

Run: `uv run pytest tests/unit/application/strategy/test_condition.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```text
feat(strategy): Condition DTO (indicator op {indicator|Decimal})
```

---

### Task 4: StrategyEntry + StrategyExit

**Files:**
- Modify: `src/cryptozavr/application/strategy/strategy_spec.py`
- Test: `tests/unit/application/strategy/test_strategy_entry.py`
- Test: `tests/unit/application/strategy/test_strategy_exit.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/application/strategy/test_strategy_entry.py
"""StrategyEntry: side + AND-conjunction of conditions."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from cryptozavr.application.strategy.enums import (
    ComparatorOp,
    IndicatorKind,
    StrategySide,
)
from cryptozavr.application.strategy.strategy_spec import (
    Condition,
    IndicatorRef,
    StrategyEntry,
)

def _c() -> Condition:
    return Condition(
        lhs=IndicatorRef(kind=IndicatorKind.SMA, period=20),
        op=ComparatorOp.GT,
        rhs=Decimal("100"),
    )

def test_minimal_long_entry() -> None:
    entry = StrategyEntry(side=StrategySide.LONG, conditions=(_c(),))
    assert entry.side is StrategySide.LONG
    assert len(entry.conditions) == 1

def test_empty_conditions_rejected() -> None:
    with pytest.raises(ValidationError):
        StrategyEntry(side=StrategySide.LONG, conditions=())

def test_more_than_eight_conditions_rejected() -> None:
    with pytest.raises(ValidationError):
        StrategyEntry(side=StrategySide.LONG, conditions=tuple(_c() for _ in range(9)))
```

```python
# tests/unit/application/strategy/test_strategy_exit.py
"""StrategyExit: OR-conjunction of conditions + optional TP/SL."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from cryptozavr.application.strategy.enums import (
    ComparatorOp,
    IndicatorKind,
)
from cryptozavr.application.strategy.strategy_spec import (
    Condition,
    IndicatorRef,
    StrategyExit,
)

def _c() -> Condition:
    return Condition(
        lhs=IndicatorRef(kind=IndicatorKind.SMA, period=20),
        op=ComparatorOp.LT,
        rhs=Decimal("100"),
    )

def test_exit_with_conditions_only() -> None:
    ex = StrategyExit(conditions=(_c(),))
    assert ex.take_profit_pct is None
    assert ex.stop_loss_pct is None

def test_exit_with_tp_sl_only() -> None:
    ex = StrategyExit(
        conditions=(),
        take_profit_pct=Decimal("0.05"),
        stop_loss_pct=Decimal("0.02"),
    )
    assert ex.take_profit_pct == Decimal("0.05")

def test_exit_requires_at_least_one_bail_out() -> None:
    with pytest.raises(ValidationError):
        StrategyExit(conditions=(), take_profit_pct=None, stop_loss_pct=None)

def test_negative_take_profit_rejected() -> None:
    with pytest.raises(ValidationError):
        StrategyExit(conditions=(_c(),), take_profit_pct=Decimal("-0.05"))

def test_negative_stop_loss_rejected() -> None:
    with pytest.raises(ValidationError):
        StrategyExit(conditions=(_c(),), stop_loss_pct=Decimal("-0.02"))
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/application/strategy/test_strategy_entry.py tests/unit/application/strategy/test_strategy_exit.py -v`
Expected: FAIL with missing symbols.

- [ ] **Step 3: Implement StrategyEntry + StrategyExit**

Append to `strategy_spec.py`:

```python
# add to imports
from cryptozavr.application.strategy.enums import StrategySide  # extend existing

class StrategyEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    side: StrategySide
    conditions: tuple[Condition, ...] = Field(min_length=1, max_length=8)

class StrategyExit(BaseModel):
    model_config = ConfigDict(frozen=True)

    conditions: tuple[Condition, ...] = Field(max_length=8, default=())
    take_profit_pct: Decimal | None = None
    stop_loss_pct: Decimal | None = None

    @model_validator(mode="after")
    def _has_bail_out_and_positive_thresholds(self) -> "StrategyExit":
        has_any = bool(self.conditions) or self.take_profit_pct is not None or self.stop_loss_pct is not None
        if not has_any:
            raise ValueError(
                "StrategyExit: provide at least one of conditions / take_profit_pct / stop_loss_pct",
            )
        if self.take_profit_pct is not None and self.take_profit_pct <= 0:
            raise ValueError("StrategyExit.take_profit_pct must be > 0 (got %r)" % self.take_profit_pct)
        if self.stop_loss_pct is not None and self.stop_loss_pct <= 0:
            raise ValueError("StrategyExit.stop_loss_pct must be > 0 (got %r)" % self.stop_loss_pct)
        return self
```

- [ ] **Step 4: Verify green**

Run: `uv run pytest tests/unit/application/strategy/test_strategy_entry.py tests/unit/application/strategy/test_strategy_exit.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```text
feat(strategy): StrategyEntry + StrategyExit (AND-entry, OR-exit + TP/SL)
```

---

### Task 5: StrategySpec aggregate + fixture + warning

**Files:**
- Modify: `src/cryptozavr/application/strategy/strategy_spec.py`
- Create: `tests/unit/application/strategy/fixtures.py`
- Test: `tests/unit/application/strategy/test_strategy_spec.py`

- [ ] **Step 1: Write fixture + failing tests**

```python
# tests/unit/application/strategy/fixtures.py
"""Canonical valid StrategySpec for tests that don't care about fields."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.application.strategy.enums import (
    ComparatorOp,
    IndicatorKind,
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
from cryptozavr.domain.venues import VenueId

def _ref(kind: IndicatorKind = IndicatorKind.SMA, period: int = 20) -> IndicatorRef:
    return IndicatorRef(kind=kind, period=period)

def valid_spec(**overrides: object) -> StrategySpec:
    base = {
        "name": "test_strategy",
        "description": "moving-average crossover with ATR stop",
        "venue": VenueId.KUCOIN,
        "symbol": Symbol.from_pair("BTC/USDT"),
        "timeframe": Timeframe.H1,
        "entry": StrategyEntry(
            side=StrategySide.LONG,
            conditions=(
                Condition(lhs=_ref(IndicatorKind.EMA, 12), op=ComparatorOp.CROSSES_ABOVE, rhs=_ref(IndicatorKind.EMA, 26)),
            ),
        ),
        "exit": StrategyExit(
            conditions=(
                Condition(lhs=_ref(IndicatorKind.EMA, 12), op=ComparatorOp.CROSSES_BELOW, rhs=_ref(IndicatorKind.EMA, 26)),
            ),
            take_profit_pct=Decimal("0.05"),
            stop_loss_pct=Decimal("0.02"),
        ),
        "size_pct": Decimal("0.25"),
    }
    base.update(overrides)
    return StrategySpec(**base)  # type: ignore[arg-type]
```

```python
# tests/unit/application/strategy/test_strategy_spec.py
"""StrategySpec: the aggregate DTO + its invariants + JSON round-trip."""

from __future__ import annotations

import warnings
from decimal import Decimal

import pytest
from pydantic import ValidationError

from cryptozavr.application.strategy.enums import (
    ComparatorOp,
    IndicatorKind,
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
from cryptozavr.domain.venues import VenueId
from tests.unit.application.strategy.fixtures import valid_spec

def test_happy_path_round_trip() -> None:
    spec = valid_spec()
    serialised = spec.model_dump()
    revived = StrategySpec.model_validate(serialised)
    assert revived == spec

def test_name_empty_rejected() -> None:
    with pytest.raises(ValidationError):
        valid_spec(name="")

def test_size_pct_zero_rejected() -> None:
    with pytest.raises(ValidationError):
        valid_spec(size_pct=Decimal("0"))

def test_size_pct_above_one_rejected() -> None:
    with pytest.raises(ValidationError):
        valid_spec(size_pct=Decimal("1.5"))

def test_version_defaults_to_one() -> None:
    spec = valid_spec()
    assert spec.version == 1

def test_model_copy_update_produces_new_instance() -> None:
    original = valid_spec()
    cloned = original.model_copy(update={"name": "cloned"})
    assert original.name == "test_strategy"
    assert cloned.name == "cloned"
    assert original.version == cloned.version

def test_frozen_cannot_mutate() -> None:
    spec = valid_spec()
    with pytest.raises(ValidationError):
        spec.name = "new_name"  # type: ignore[misc]

def test_long_period_on_short_timeframe_emits_warning() -> None:
    """500-period RSI on 1-minute candles is >7 days of warm-up — very
    likely user error. Should warn, not fail, because the same ratio on
    daily candles is legit long-trend."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        StrategySpec(
            name="noisy",
            description="500 RSI on 1m",
            venue=VenueId.KUCOIN,
            symbol=Symbol.from_pair("BTC/USDT"),
            timeframe=Timeframe.M1,
            entry=StrategyEntry(
                side=StrategySide.LONG,
                conditions=(
                    Condition(
                        lhs=IndicatorRef(kind=IndicatorKind.RSI, period=500),
                        op=ComparatorOp.LT,
                        rhs=Decimal("30"),
                    ),
                ),
            ),
            exit=StrategyExit(conditions=(), take_profit_pct=Decimal("0.05")),
            size_pct=Decimal("0.1"),
        )
    assert any(issubclass(w.category, UserWarning) and "warm-up" in str(w.message) for w in caught)

def test_long_period_on_long_timeframe_no_warning() -> None:
    """200-period SMA on daily candles = 200 days of warm-up — canonical
    long-trend filter, no warning."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        StrategySpec(
            name="canonical_200d",
            description="200-day SMA trend",
            venue=VenueId.KUCOIN,
            symbol=Symbol.from_pair("BTC/USDT"),
            timeframe=Timeframe.D1,
            entry=StrategyEntry(
                side=StrategySide.LONG,
                conditions=(
                    Condition(
                        lhs=IndicatorRef(kind=IndicatorKind.SMA, period=200),
                        op=ComparatorOp.GT,
                        rhs=Decimal("0"),
                    ),
                ),
            ),
            exit=StrategyExit(conditions=(), stop_loss_pct=Decimal("0.1")),
            size_pct=Decimal("0.1"),
        )
    assert not any("warm-up" in str(w.message) for w in caught)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/application/strategy/test_strategy_spec.py -v`
Expected: FAIL on `ImportError: StrategySpec`.

- [ ] **Step 3: Implement StrategySpec**

Add to `strategy_spec.py`:

```python
# top-level imports
import warnings
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.domain.venues import VenueId

_WARM_UP_WARNING_THRESHOLD_MS = 7 * 24 * 60 * 60 * 1000  # 7 days

class StrategySpec(BaseModel):
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

    @model_validator(mode="after")
    def _warn_on_excessive_warm_up(self) -> "StrategySpec":
        interval_ms = self.timeframe.to_milliseconds()
        for cond in (*self.entry.conditions, *self.exit.conditions):
            for ref in (cond.lhs, cond.rhs):
                if not isinstance(ref, IndicatorRef):
                    continue
                if ref.period * interval_ms > _WARM_UP_WARNING_THRESHOLD_MS:
                    warnings.warn(
                        f"StrategySpec: indicator {ref.kind.value}({ref.period}) on "
                        f"{self.timeframe.value} timeframe implies warm-up >7 days",
                        UserWarning,
                        stacklevel=2,
                    )
                    return self  # one warning per spec is enough
        return self
```

`Symbol` is not a Pydantic model (frozen dataclass) so we need
`arbitrary_types_allowed=True`. `Timeframe` is a `StrEnum` which Pydantic
handles natively.

- [ ] **Step 4: Verify green**

Run: `uv run pytest tests/unit/application/strategy/test_strategy_spec.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```text
feat(strategy): StrategySpec aggregate + warm-up warning
```

---

### Task 6: StrategySpecBuilder

**Files:**
- Create: `src/cryptozavr/application/strategy/builder.py`
- Test: `tests/unit/application/strategy/test_builder.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/application/strategy/test_builder.py
"""StrategySpecBuilder: fluent, immutable, build() validates."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from cryptozavr.application.strategy.builder import StrategySpecBuilder
from cryptozavr.application.strategy.enums import (
    ComparatorOp,
    IndicatorKind,
    StrategySide,
)
from cryptozavr.application.strategy.strategy_spec import (
    Condition,
    IndicatorRef,
)
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.domain.venues import VenueId

def _entry_cond() -> Condition:
    return Condition(
        lhs=IndicatorRef(kind=IndicatorKind.EMA, period=12),
        op=ComparatorOp.CROSSES_ABOVE,
        rhs=IndicatorRef(kind=IndicatorKind.EMA, period=26),
    )

def _exit_cond() -> Condition:
    return Condition(
        lhs=IndicatorRef(kind=IndicatorKind.EMA, period=12),
        op=ComparatorOp.CROSSES_BELOW,
        rhs=IndicatorRef(kind=IndicatorKind.EMA, period=26),
    )

def _fully_built() -> StrategySpecBuilder:
    return (
        StrategySpecBuilder()
        .with_name("crossover")
        .with_description("EMA12 crossing EMA26")
        .with_market(
            venue=VenueId.KUCOIN,
            symbol=Symbol.from_pair("BTC/USDT"),
            timeframe=Timeframe.H1,
        )
        .with_entry(side=StrategySide.LONG, conditions=(_entry_cond(),))
        .with_exit(
            conditions=(_exit_cond(),),
            take_profit_pct=Decimal("0.05"),
            stop_loss_pct=Decimal("0.02"),
        )
        .with_size_pct(Decimal("0.25"))
    )

def test_builder_builds_valid_spec() -> None:
    spec = _fully_built().build()
    assert spec.name == "crossover"
    assert spec.size_pct == Decimal("0.25")

def test_builder_missing_market_rejected_at_build() -> None:
    incomplete = (
        StrategySpecBuilder()
        .with_name("x")
        .with_description("y")
        .with_entry(side=StrategySide.LONG, conditions=(_entry_cond(),))
        .with_exit(conditions=(_exit_cond(),))
        .with_size_pct(Decimal("0.1"))
    )
    with pytest.raises(ValidationError):
        incomplete.build()

def test_builder_is_immutable_per_step() -> None:
    b1 = StrategySpecBuilder().with_name("alpha")
    b2 = b1.with_name("beta")
    spec_alpha = (
        b1.with_description("d")
        .with_market(
            venue=VenueId.KUCOIN,
            symbol=Symbol.from_pair("BTC/USDT"),
            timeframe=Timeframe.H1,
        )
        .with_entry(side=StrategySide.LONG, conditions=(_entry_cond(),))
        .with_exit(conditions=(_exit_cond(),))
        .with_size_pct(Decimal("0.1"))
        .build()
    )
    assert spec_alpha.name == "alpha"
    # b2 was not used but b1 still produces "alpha" — confirms isolation
    assert b2 is not b1

def test_builder_matches_direct_construction() -> None:
    from tests.unit.application.strategy.fixtures import valid_spec  # local

    built = (
        StrategySpecBuilder()
        .with_name("test_strategy")
        .with_description("moving-average crossover with ATR stop")
        .with_market(
            venue=VenueId.KUCOIN,
            symbol=Symbol.from_pair("BTC/USDT"),
            timeframe=Timeframe.H1,
        )
        .with_entry(
            side=StrategySide.LONG,
            conditions=(
                Condition(
                    lhs=IndicatorRef(kind=IndicatorKind.EMA, period=12),
                    op=ComparatorOp.CROSSES_ABOVE,
                    rhs=IndicatorRef(kind=IndicatorKind.EMA, period=26),
                ),
            ),
        )
        .with_exit(
            conditions=(
                Condition(
                    lhs=IndicatorRef(kind=IndicatorKind.EMA, period=12),
                    op=ComparatorOp.CROSSES_BELOW,
                    rhs=IndicatorRef(kind=IndicatorKind.EMA, period=26),
                ),
            ),
            take_profit_pct=Decimal("0.05"),
            stop_loss_pct=Decimal("0.02"),
        )
        .with_size_pct(Decimal("0.25"))
        .build()
    )
    assert built == valid_spec()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/application/strategy/test_builder.py -v`
Expected: FAIL on `ImportError`.

- [ ] **Step 3: Implement StrategySpecBuilder**

```python
# src/cryptozavr/application/strategy/builder.py
"""Fluent, immutable builder for StrategySpec.

Each `with_*` returns a new builder so partially-built specs don't
alias. Validation is deferred to `.build()` which constructs the full
StrategySpec in one shot (Pydantic validates the aggregate atomically).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Self

from cryptozavr.application.strategy.enums import StrategySide
from cryptozavr.application.strategy.strategy_spec import (
    Condition,
    StrategyEntry,
    StrategyExit,
    StrategySpec,
)
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.domain.venues import VenueId

@dataclass(frozen=True, slots=True)
class StrategySpecBuilder:
    _name: str | None = None
    _description: str | None = None
    _venue: VenueId | None = None
    _symbol: Symbol | None = None
    _timeframe: Timeframe | None = None
    _entry: StrategyEntry | None = None
    _exit: StrategyExit | None = None
    _size_pct: Decimal | None = None
    _version: int = 1

    def with_name(self, name: str) -> Self:
        return replace(self, _name=name)

    def with_description(self, description: str) -> Self:
        return replace(self, _description=description)

    def with_market(
        self,
        *,
        venue: VenueId,
        symbol: Symbol,
        timeframe: Timeframe,
    ) -> Self:
        return replace(self, _venue=venue, _symbol=symbol, _timeframe=timeframe)

    def with_entry(
        self,
        *,
        side: StrategySide,
        conditions: Iterable[Condition],
    ) -> Self:
        return replace(
            self,
            _entry=StrategyEntry(side=side, conditions=tuple(conditions)),
        )

    def with_exit(
        self,
        *,
        conditions: Iterable[Condition] = (),
        take_profit_pct: Decimal | None = None,
        stop_loss_pct: Decimal | None = None,
    ) -> Self:
        return replace(
            self,
            _exit=StrategyExit(
                conditions=tuple(conditions),
                take_profit_pct=take_profit_pct,
                stop_loss_pct=stop_loss_pct,
            ),
        )

    def with_size_pct(self, pct: Decimal) -> Self:
        return replace(self, _size_pct=pct)

    def with_version(self, version: int) -> Self:
        return replace(self, _version=version)

    def build(self) -> StrategySpec:
        # Pydantic raises ValidationError for any None where the field is
        # required — the error surface matches direct construction, so MCP
        # callers in 2D see the same diagnostics.
        return StrategySpec(
            name=self._name,  # type: ignore[arg-type]
            description=self._description,  # type: ignore[arg-type]
            venue=self._venue,  # type: ignore[arg-type]
            symbol=self._symbol,  # type: ignore[arg-type]
            timeframe=self._timeframe,  # type: ignore[arg-type]
            entry=self._entry,  # type: ignore[arg-type]
            exit=self._exit,  # type: ignore[arg-type]
            size_pct=self._size_pct,  # type: ignore[arg-type]
            version=self._version,
        )
```

The `field(...)` import is unused in my current draft; remove if so.

- [ ] **Step 4: Verify green**

Run: `uv run pytest tests/unit/application/strategy/test_builder.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```text
feat(strategy): StrategySpecBuilder (fluent, immutable, build-time validation)
```

---

### Task 7: CHANGELOG + full verification sweep + PR

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add `[Unreleased]` entry**

```markdown
## [Unreleased]

### Added
- **Phase 2A** — `StrategySpec` DSL (Pydantic v2 frozen) + `StrategySpecBuilder`
  (fluent, immutable). Declarative trading strategy description with
  `IndicatorRef` / `Condition` / `StrategyEntry` / `StrategyExit`
  sub-DTOs. Invariants enforced at construction (non-empty entry
  conditions, at-least-one exit path, `size_pct ∈ (0, 1]`, warm-up
  warning for `period × timeframe > 7 days`). Pattern #16 (Builder)
  shipped. No MCP tools / persistence / execution — those land in
  2D / 2E / 2B respectively.
```

- [ ] **Step 2: Run full verification sweep**

```bash
uv run pytest tests/unit tests/contract -m "not integration" -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

Expected: all green. Tests count should be ~515 (2C baseline) + ~40 (2A) ≈ 555.

- [ ] **Step 3: Push branch + create PR**

```bash
git push -u origin feat/phase-2a-strategy-spec
gh pr create --title "Phase 2A: StrategySpec DSL + Builder" --body-file /tmp/pr-body.md
```

PR body includes: summary, test count delta, pattern (#16 Builder),
links to spec file, CI expectation.

---

## Self-Review

1. **Spec coverage:** Every "Locked decision" has a test — IndicatorKind
   members (Task 1), Timeframe reuse (fixture imports domain's),
   `size_pct` fraction invariant (Task 5), AND-entry (Task 4), cloning
   via `model_copy` (Task 5), warm-up warning (Task 5 + negative test).
2. **Placeholder scan:** No TBD/TODO. Every step has concrete code.
3. **Type consistency:** `Symbol` uses `arbitrary_types_allowed=True`;
   `Timeframe` is `StrEnum` (native Pydantic); `VenueId` same.
   `Builder` field names prefixed `_` to avoid Pydantic picking them
   up if we ever change the builder to a `BaseModel` (dataclass today).
4. **Target test count:** ~40. Actual after Task 6: 5 (enums) + 5
   (indicator_ref) + 4 (condition) + 3 (entry) + 5 (exit) + 9 (spec)
   + 4 (builder) = 35 unit tests. Spec says ≥40. Add 5 property tests
   in Task 6 Step 3 if count is short: spec round-trip idempotency,
   builder commutativity for independent `with_*` steps, etc.

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-04-22-phase-2a-strategy-spec.md`.
Execution via **superpowers:executing-plans** (inline, batch-with-checkpoints).
