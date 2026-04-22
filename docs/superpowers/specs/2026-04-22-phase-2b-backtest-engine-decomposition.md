# Phase 2B — BacktestEngine decomposition

> **Status:** DECOMPOSITION PROPOSAL — not a committed design. 2B is the
> natural consumer of 2A's `StrategySpec` (input) and producer of 2C's
> `BacktestReport` (output). It's also big enough that shipping it as one
> PR would violate the brainstorming skill's single-subsystem rule. This
> doc breaks it into 4 sub-phases, each of which gets its own
> spec / plan / PR cycle.

## Why decompose?

The MVP spec (§Phase 2, line 1465) lists 2B as one line: "BacktestEngine
с slippage/fee simulation". Unpacking that line reveals five largely
independent subsystems:

1. **Indicator engine** — compute SMA / EMA / RSI / MACD / ATR / VOLUME
   over a candle stream. Pure math, testable with hand-built series.
2. **Condition evaluator** — apply `Condition` / `StrategyEntry` /
   `StrategyExit` to a single bar given current + previous indicator
   values. Stateful because `CROSSES_ABOVE` needs the last bar.
3. **Trade simulator** — position lifecycle (open, track, close on
   condition/TP/SL), slippage model, fee model, equity-curve update.
4. **BacktestEngine facade** — wire 1+2+3 together, consume candles,
   emit `BacktestReport` (already-defined DTO in 2C).
5. **Indicator value cache** (optional, may fold into #1) — rolling
   window storage so SMA(20) doesn't re-scan 20 bars per step.

Each is testable in isolation with a DI-friendly interface; shipping them
as separate PRs keeps reviews digestible.

## Proposed sub-phase sequence

### 2B.1 — Indicator engine

- `cryptozavr.application.backtest.indicators/` package.
- One class per `IndicatorKind` implementing `Indicator.update(bar) -> Decimal | None`.
- `IndicatorFactory` resolves `IndicatorRef` → `Indicator` instance.
- Hypothesis tests for "SMA equals numpy reference on 100 random candles".
- No `StrategySpec` or `BacktestReport` touched.

**Acceptance:** ≥30 unit tests covering each indicator + factory; ruff/
mypy clean; no regressions elsewhere.

### 2B.2 — Condition evaluator

- Consumes the indicator outputs from 2B.1 and evaluates `Condition`s
  with `CROSSES_*` state ("did the relationship flip this bar?").
- `StrategyEntryEvaluator` / `StrategyExitEvaluator` glue.
- Small state machine for crossings; hypothesis tests generate random
  indicator series and assert `CROSSES_ABOVE ⇔ (prev <= rhs AND curr > rhs)`.

**Acceptance:** ≥20 unit tests; no backtest execution yet.

### 2B.3 — Trade simulator + slippage + fees

- `TradeSimulator` owns one open position at a time (Phase 2 is
  single-symbol / single-position; multi-symbol is Phase 4+).
- Entry price with slippage model (`PctSlippageModel` / `SpreadSlippageModel`).
- Exit on: exit condition true, TP pct hit intrabar, SL pct hit intrabar.
- Fee model (`FixedBpsFeeModel` initially — maker/taker asymmetry deferred).
- Emits `BacktestTrade`s + appends to equity curve.

**Acceptance:** ≥25 unit tests including TP-before-SL vs SL-before-TP
intrabar edge cases; slippage + fee math verified against hand-computed
references.

### 2B.4 — BacktestEngine facade

- `BacktestEngine.run(spec: StrategySpec, candles: Iterable[OHLCVCandle])
  -> BacktestReport`.
- Orchestrates: per-bar → update indicators (2B.1) → evaluate conditions
  (2B.2) → advance simulator (2B.3) → record equity.
- Integration-style test: run a full spec on synthetic trending candles,
  assert `TotalReturnVisitor().visit(report) > 0`.

**Acceptance:** ≥10 integration tests against hand-built market data;
smoke-test via all 5 visitors from 2C on the produced report.

## Open questions to resolve per sub-phase

### 2B.1 (indicator engine)
- **MACD** is three values (line, signal, histogram). How does the DSL
  reference sub-component? Either `IndicatorKind.MACD_LINE` / `MACD_SIGNAL`
  / `MACD_HIST` (enum split) or a `field: str` annotation on `IndicatorRef`.
- Streaming vs. batch API? Streaming is simpler to plug into the engine
  facade; batch is easier for testing.

### 2B.2 (condition evaluator)
- Who owns the "previous value" state — the condition or a per-spec
  evaluator? Per-spec is cleaner (condition stays pure), but needs
  one extra indirection layer.
- Warm-up handling: if an indicator hasn't emitted yet (not enough
  bars), evaluator should return `no-signal` (not `false`). Spelling?

### 2B.3 (trade simulator)
- Intrabar TP/SL precedence when both triggered in the same candle:
  assume worst-case (SL wins for long), or model via high-then-low
  walk? MVP = worst-case; document the assumption.
- Partial fills deferred to Phase 5 (live execution).
- Position sizing when `size_pct * equity < min_notional` (dust
  positions) — skip trade vs. round up? MVP = skip with log warning.

### 2B.4 (engine facade)
- Candle source API — sync iterable vs. async iterable? 2C visitors
  are sync; easier if 2B.4 is sync too. Async mode is a Phase 4 concern
  (live paper trading).
- Progress callback / cancellation — out of scope for MVP (run time
  should be sub-second for sensible inputs).

## What this decomposition does NOT cover

- **Multi-symbol backtest** (portfolio). Phase 4+.
- **Walk-forward / cross-validation.** Phase 2+.
- **MCP tool surface** (`backtest_strategy`, `compare_strategies`).
  Phase 2D.
- **Persistence** of `BacktestReport`. Phase 2E.
- **Stress test** with synthetic adverse scenarios. Phase 2+.

## Acceptance for "Phase 2B complete"

All four sub-phases merged to `main` with green suite. Combined additions:
~90-120 new unit tests, ~10 new integration tests, no regressions in
the 555-test post-2A baseline. Next recommended phase is 2D (MCP surface
over 2A + 2B + 2C).

## Skill usage (per Ralph directive "под каждую задучу юзай подходящий скилл")

Each sub-phase goes through the same chain:
`brainstorming` → `writing-plans` → `executing-plans` (with `test-driven-development`)
→ `pr-review-toolkit:review-pr` → `receiving-code-review` → merge.

`superpowers:systematic-debugging` when a test flakes (especially 2B.3
intrabar edge cases) and `verification-before-completion` before any
commit/PR.
