# Phase 2B.1 — Indicator Engine (design)

> **Status:** LOCKED. Ralph-loop iteration — solo-brainstormed with
> conservative defaults on ambiguous points. Output contract exposed
> as a Protocol so future phases can swap implementations.

## Goal

Ship `cryptozavr.application.backtest.indicators` — stateful streaming
indicators that consume `OHLCVCandle`s one-at-a-time and emit the
latest value. The package is the pure-math foundation for the condition
evaluator (2B.2) and trade simulator (2B.3).

## Non-goals

- **Not a historical "recompute-from-window" API.** We stream; if 2B
  callers need historical values they keep their own rolling log.
- **No `StrategySpec` imports.** This layer consumes raw candles only.
  The `IndicatorRef` → `Indicator` mapping lives in `IndicatorFactory`,
  a pure look-up.
- **No cross-timeframe aggregation.** An indicator is tied to the same
  cadence as the candle stream driving it.
- **No financial-accuracy promises beyond stated algorithms.** We match
  the textbook formula, not a specific vendor's quirk.

## Architecture

```text
src/cryptozavr/application/backtest/
├── __init__.py
└── indicators/
    ├── __init__.py
    ├── base.py          # Indicator Protocol, IndicatorOutput
    ├── sma.py           # SimpleMovingAverage
    ├── ema.py           # ExponentialMovingAverage
    ├── rsi.py           # RelativeStrengthIndex
    ├── macd.py          # MACD (line + signal + histogram triple)
    ├── atr.py           # AverageTrueRange
    ├── volume.py        # VolumeIndicator (identity on candle.volume)
    ├── price.py         # PriceSource extractor (open/high/low/close/hlc3)
    └── factory.py       # IndicatorFactory: IndicatorRef -> Indicator
```

## The `Indicator` Protocol

```python
from typing import Protocol
from decimal import Decimal
from cryptozavr.domain.market_data import OHLCVCandle

class Indicator(Protocol):
    """Streaming indicator: feed one candle, get the latest value (or None
    while warming up)."""

    def update(self, candle: OHLCVCandle) -> Decimal | None: ...

    @property
    def is_warm(self) -> bool:
        """True once the indicator has consumed enough bars to emit."""
        ...

    @property
    def period(self) -> int: ...
```

Key contract decisions (locked):

1. **Return `None` during warm-up**, concrete `Decimal` once warm.
   Mirrors the 2C `None`-vs-`Decimal("0")` pattern (distinguishes
   "no value yet" from "value happens to be zero").
2. **`update()` is stateful and not idempotent** — calling twice with
   the same candle advances the window twice. Engine callers MUST feed
   each candle exactly once.
3. **No rewind / reset.** If the backtest engine needs to re-run, it
   creates a fresh indicator instance. Simpler than state-management.

## MACD: three values, one `update`

MACD canonically returns a triple (line, signal, histogram). Rather than
force three enum members (`MACD_LINE` / `MACD_SIGNAL` / `MACD_HIST`) on
`IndicatorKind`, we keep the enum clean and ship a **`MACDIndicator`
that returns `Decimal | None` for the MACD line** (the most commonly
referenced value). Access to signal + histogram is deferred to 2B.2
when we discover a strategy spec actually needs it.

Rationale: YAGNI. None of the canonical `IndicatorRef`-consuming
setups we'd ship in 2D's first wave of MCP tools depend on the signal
line being exposed in the DSL. When one does, we add it as an additive
enum change.

## `PriceSource` extraction

Each indicator takes a `PriceSource` at construction and, per candle,
extracts the input value:

```python
PriceSource.OPEN  → candle.open
PriceSource.HIGH  → candle.high
PriceSource.LOW   → candle.low
PriceSource.CLOSE → candle.close
PriceSource.HLC3  → (candle.high + candle.low + candle.close) / 3
```

`HLC3` uses `Decimal("3")` exact division — no float precision loss.

## Indicator algorithms (locked formulas)

### SimpleMovingAverage(period, source)

```text
SMA_t = sum(source(candle_{t-period+1..t})) / period
warm after: period bars
```

Rolling deque of size `period`; update pops oldest and appends newest;
sum is maintained incrementally (O(1) per update, not O(period)).

### ExponentialMovingAverage(period, source)

```text
alpha = Decimal(2) / Decimal(period + 1)
EMA_t = alpha * source_t + (Decimal(1) - alpha) * EMA_{t-1}
EMA_0 (after warm-up) = SMA of first `period` bars
warm after: period bars
```

### RelativeStrengthIndex(period=14, source=CLOSE)

```javascript
gain_t = max(source_t - source_{t-1}, 0)
loss_t = max(source_{t-1} - source_t, 0)
avg_gain_0 = mean(gain_{1..period})
avg_loss_0 = mean(loss_{1..period})
# Wilder smoothing after warm-up:
avg_gain_t = (avg_gain_{t-1} * (period-1) + gain_t) / period
avg_loss_t = (avg_loss_{t-1} * (period-1) + loss_t) / period
rs_t = avg_gain_t / avg_loss_t   (Decimal, or +inf-like => RSI=100 if avg_loss==0)
RSI_t = 100 - 100 / (1 + rs_t)
warm after: period+1 bars (need period deltas)
```

Edge case: `avg_loss == 0` → RSI = 100 by convention (max bullish).

### MACD(fast=12, slow=26, signal=9, source=CLOSE)

```bash
fast_ema_t = EMA(fast, source)
slow_ema_t = EMA(slow, source)
macd_line_t = fast_ema_t - slow_ema_t           # returned from update()
(signal / histogram internally computed but NOT exposed in 2B.1)
warm after: slow bars
```

### AverageTrueRange(period=14)

```bash
tr_t = max(high_t - low_t,
           |high_t - close_{t-1}|,
           |low_t - close_{t-1}|)
ATR_0 (after warm-up) = mean(tr_{1..period})
ATR_t = (ATR_{t-1} * (period-1) + tr_t) / period     # Wilder smoothing
warm after: period+1 bars (need one prior close for TR)
```

Unlike SMA/EMA, ATR is **not parameterised by `PriceSource`** — true
range is an OHLC-specific concept.

### Volume(source=VOLUME — self-documenting)

```text
Volume_t = candle.volume
warm after: 1 bar (trivial)
```

Exists as an `Indicator` for uniform factory treatment; strategies that
compare `VOLUME > threshold` need an `Indicator` instance to plug into
the condition evaluator.

## `IndicatorFactory`

```python
def create(ref: IndicatorRef) -> Indicator:
    match ref.kind:
        case IndicatorKind.SMA:    return SimpleMovingAverage(ref.period, ref.source)
        case IndicatorKind.EMA:    return ExponentialMovingAverage(ref.period, ref.source)
        case IndicatorKind.RSI:    return RelativeStrengthIndex(ref.period, ref.source)
        case IndicatorKind.MACD:   return MACD(fast=12, slow=ref.period, signal=9, source=ref.source)
        case IndicatorKind.ATR:    return AverageTrueRange(ref.period)  # source ignored
        case IndicatorKind.VOLUME: return VolumeIndicator()             # source/period ignored
```

MACD uses `ref.period` as the slow EMA period (12/26 canonical → period=26
default in typical use; user can override via `IndicatorRef(kind=MACD, period=52)`).
Fast and signal periods are fixed at 12 and 9 — adding them as knobs
requires a DSL extension (2A+1).

## Test plan (target ≥ 40 unit tests)

Per indicator — ~5-8 tests:
- Returns `None` during warm-up.
- Returns concrete `Decimal` on first warm bar; matches hand-computed
  reference.
- Matches numerically-stable reference on a 50-bar synthetic series.
- `is_warm` transitions at the correct bar.
- Property test: value stays finite across random bounded inputs
  (hypothesis).

Factory — ~6 tests:
- Each `IndicatorKind` creates the right concrete type.
- `period` passes through.
- Independent instances do not share state (two SMA(20)s can run in
  parallel over different candles).

Price source — ~5 tests:
- Each `PriceSource` extracts the right field.
- HLC3 uses exact Decimal division.

## Acceptance for 2B.1

- `cryptozavr.application.backtest.indicators` package ships the
  `Indicator` Protocol + 6 concretes + factory + price extractor.
- ≥ 40 unit tests (happy path, warm-up semantics, hand-computed
  reference checks, hypothesis).
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src` green.
- No regressions — total suite stays green at 555 + ~40 new.
- CHANGELOG `[Unreleased]` entry for 2B.1.
