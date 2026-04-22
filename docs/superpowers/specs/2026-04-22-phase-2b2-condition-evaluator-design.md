# Phase 2B.2 — Condition Evaluator (design)

> **Status:** LOCKED. Second sub-phase of the 2B decomposition
> (see `2026-04-22-phase-2b-backtest-engine-decomposition.md`).
> Consumes 2B.1's `Indicator` outputs; produces bool signals for
> 2B.3's trade simulator.

## Goal

Ship `cryptozavr.application.backtest.evaluator` — given a `StrategySpec`,
a candle stream, and an engine that drives all referenced `Indicator`s,
tell the trade simulator: **should I enter now?** and **should I exit now?**.

## Non-goals

- **No position tracking.** The evaluator is stateless w.r.t. portfolio
  state. It answers "is the entry signal true this bar?" regardless of
  whether a position is already open. 2B.3 decides what to do with that.
- **No indicator math.** All compute lives in 2B.1. The evaluator owns
  a cache (`IndicatorRef → Indicator`) so the same `IndicatorRef` used
  in entry + exit only gets one computation stream, not two.
- **No trade simulation, no equity.** Those are 2B.3.

## Architecture

```text
src/cryptozavr/application/backtest/evaluator/
├── __init__.py
├── signals.py           # SignalTick NamedTuple, EntrySignal/ExitSignal enums
├── indicator_cache.py   # IndicatorCache: IndicatorRef -> Indicator (interned)
├── condition.py         # evaluate_condition(condition, cache, prev_cache) -> bool | None
└── strategy_evaluator.py  # StrategyEvaluator: feed candle, get signals
```

Tests in `tests/unit/application/backtest/evaluator/`.

## Core concepts

### SignalTick

```python
@dataclass(frozen=True, slots=True)
class SignalTick:
    bar_index: int            # 0-based; useful for debugging
    entry_signal: bool | None # None while any indicator still warming up
    exit_signal: bool | None  # None while any indicator still warming up
```

`None` propagates during warm-up so callers (2B.3) can distinguish
"no signal yet" from "signal is false".

### IndicatorCache

A `StrategySpec` often references the same `IndicatorRef` in entry and
exit (e.g. EMA12 crossing EMA26 is the entry; EMA12 crossing BELOW EMA26
is the exit). Computing each twice would be both wasteful and wrong
(two parallel streams desynchronise if one is `update`d before the other).

The cache:
- Interns `IndicatorRef` → `Indicator` (one concrete stream per unique ref).
- `IndicatorRef.__eq__` + `__hash__` already work (Pydantic frozen model).
- Call `cache.tick(candle)` once per bar to advance every interned indicator.
- Look up values via `cache.current_value(ref) -> Decimal | None`.

### Previous-bar cache

`CROSSES_ABOVE` / `CROSSES_BELOW` need both current and previous bar
indicator values. The cache snapshots `current_value` at the end of
each `tick()` into `previous_value` so `evaluate_condition` can use
both.

```python
class IndicatorCache:
    def tick(self, candle: OHLCVCandle) -> None: ...
    def current_value(self, ref: IndicatorRef) -> Decimal | None: ...
    def previous_value(self, ref: IndicatorRef) -> Decimal | None: ...
    def all_warm(self) -> bool: ...
```

### Condition evaluation semantics

| Op | Evaluates |
|---|---|
| `GT` | `lhs > rhs` (current bar) |
| `GTE` | `lhs >= rhs` |
| `LT` | `lhs < rhs` |
| `LTE` | `lhs <= rhs` |
| `CROSSES_ABOVE` | `prev_lhs <= prev_rhs AND curr_lhs > curr_rhs` |
| `CROSSES_BELOW` | `prev_lhs >= prev_rhs AND curr_lhs < curr_rhs` |

Returns `None` when:
- Any referenced `IndicatorRef`'s `current_value` is None (warming up), OR
- A crossing op has no `previous_value` yet (first warm bar).

Returns `bool` once fully warm.

### StrategyEntry / StrategyExit evaluation

Entry (AND-of-conditions): all `bool`-evaluating conditions must be True.
Any `None` ⇒ return `None`. All-False ⇒ `False`. All-True ⇒ `True`.

Exit (OR-of-conditions + optional TP/SL): **2B.2 only evaluates the
condition list**. TP/SL are percentage bounds against the entry price —
that's trade-simulator territory (2B.3) because only 2B.3 knows the
entry price. 2B.2 returns "any exit condition true?" with `None`-
propagation identical to entry.

## StrategyEvaluator API

```python
class StrategyEvaluator:
    def __init__(self, spec: StrategySpec) -> None:
        """Allocates the IndicatorCache, pre-warms refs from entry + exit."""

    def tick(self, candle: OHLCVCandle) -> SignalTick:
        """Advance all indicators, evaluate entry + exit, return SignalTick."""

    @property
    def is_warm(self) -> bool:
        """True once every referenced indicator has emitted at least once
        AND (if any crossing op used) has at least two values in history."""
```

Construction pre-registers every `IndicatorRef` reachable through the
spec so `tick()` is O(num_conditions) rather than re-scanning the spec.

## Test plan (target ≥ 35 unit tests)

### `IndicatorCache` — ~10 tests
- Same ref twice → same Indicator instance (interning).
- Different refs → different instances.
- `current_value` returns None while indicator warming, Decimal once warm.
- `previous_value` returns None on first warm bar; returns last bar's
  value afterward.
- `all_warm` transitions at the right bar.
- `tick()` called 0 times ⇒ all values None.

### `evaluate_condition` — ~12 tests
- Each `ComparatorOp` gets at least one True + one False case.
- Decimal-constant RHS path (e.g. `RSI < 30`).
- Crossing ops need `previous_value`; return None when unavailable.
- Warm-up propagation: if `lhs` not warm → None (even if `rhs` is a
  Decimal constant).

### `StrategyEvaluator` — ~13 tests
- Happy path: EMA crossover emits `entry_signal=True` at the crossing bar.
- Exit signal emits True on the reverse crossing.
- Warm-up ticks return `SignalTick(entry=None, exit=None)`.
- Same-reference entry + exit share one stream (verify by running a
  parallel Indicator side-by-side and asserting identical values).
- `is_warm` transitions correctly.
- Property test (hypothesis): synthetic random candle streams never
  raise; signals remain `bool | None`.

## Acceptance for 2B.2

- All modules under Architecture exist + pass type-checks.
- ≥ 35 new unit tests; total suite 603 + ~35 ≈ 638.
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src` green.
- CHANGELOG `[Unreleased]` entry.

## Open questions — locked to defaults

1. **Interning key for IndicatorCache** — Pydantic `IndicatorRef` is
   already hashable (frozen). Use it directly. No custom hash needed.
2. **Warm-up strictness** — must *all* referenced indicators be warm
   before emitting a bool signal, or emit per-condition partial? Locked:
   strict (all-or-none). Simpler; avoids accidental half-signals.
3. **Same-bar crossing** — a condition evaluated exactly on the bar
   where `prev_lhs == prev_rhs AND curr_lhs > curr_rhs` — does
   `CROSSES_ABOVE` fire? Locked: **yes**, per canonical definition
   (`prev <= rhs AND curr > rhs`). The `<=` on the left side catches
   the equal-then-cross edge.
