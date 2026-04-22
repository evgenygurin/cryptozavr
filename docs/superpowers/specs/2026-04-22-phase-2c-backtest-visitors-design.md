# Phase 2C — Post-backtest analytics via Visitor pattern

> **Status:** draft (2026-04-22). Entry point into Phase 2 per user directive
> "сначала C, потом A". This is a **contract-first** slice: the data model
> is designed now so that 2B's future `BacktestEngine` only has to populate
> it, and the visitor surface is usable today against mock `BacktestReport`s.

## Goal

Produce a small, independently-testable analytics layer that computes the
standard post-backtest metrics (Sharpe, max drawdown, win rate, profit
factor, total return) from a `BacktestReport` DTO. The layer MUST:

1. Not depend on anything from 2B (backtest execution) or 2A (strategy DSL).
2. Expose a Visitor protocol so Phase 2+ can add metrics without touching
   existing visitors or the composer.
3. Ship with property-based tests for the arithmetic-sensitive metrics
   (Sharpe, max drawdown) so numeric regressions are caught immediately.

## Non-goals

- No MCP tools. The `compare_strategies` / `backtest_strategy` tools belong
  to 2D; this slice is standalone.
- No persistence. `strategy_specs` / `backtest_reports` tables live in 2E.
- No backtest execution. The DTO is populated by 2B later; for 2C we
  construct reports in tests.
- No price/volatility *normalisation*. Sharpe assumes daily returns; callers
  aggregate beforehand.

## Architecture

New sub-package `src/cryptozavr/application/analytics/`:

```text
src/cryptozavr/application/analytics/
├── __init__.py
├── backtest_report.py          # BacktestReport, BacktestTrade, EquityPoint, TradeSide
├── visitors/
│   ├── __init__.py
│   ├── base.py                 # BacktestVisitor Protocol[T_co]
│   ├── sharpe.py               # SharpeRatioVisitor → Decimal
│   ├── max_drawdown.py         # MaxDrawdownVisitor → Decimal (pct, 0..1)
│   ├── win_rate.py             # WinRateVisitor → Decimal (pct, 0..1)
│   ├── profit_factor.py        # ProfitFactorVisitor → Decimal | None
│   └── total_return.py         # TotalReturnVisitor → Decimal
└── analytics_service.py        # BacktestAnalyticsService composer
```

Tests in `tests/unit/application/analytics/` mirror the layout
(one test module per visitor + `test_analytics_service.py`).

## Data model (`backtest_report.py`)

```python
class TradeSide(StrEnum):
    LONG = "long"
    SHORT = "short"

@dataclass(frozen=True, slots=True)
class BacktestTrade:
    opened_at: Instant
    closed_at: Instant
    side: TradeSide
    entry_price: Decimal
    exit_price: Decimal
    size: Decimal              # base-currency qty
    pnl: Decimal               # realised in quote currency (fees already applied)

@dataclass(frozen=True, slots=True)
class EquityPoint:
    observed_at: Instant
    equity: Decimal

@dataclass(frozen=True, slots=True)
class BacktestReport:
    strategy_name: str
    period: TimeRange
    initial_equity: Decimal
    final_equity: Decimal
    trades: tuple[BacktestTrade, ...]
    equity_curve: tuple[EquityPoint, ...]
```

Design choices:

- All frozen / slots for hashability and cheap identity comparison.
- `equity_curve` is a tuple (not list) — callers can safely share.
- `trades` ordered chronologically by `opened_at`; enforced in `__post_init__`.
- No `__post_init__` validation of `equity_curve` ordering for MVP; add
  if a test surfaces a real regression.
- PnL is post-fees — simulators are responsible for applying fees before
  building a `BacktestTrade`. Keeps visitors fee-model-agnostic.

## Visitor protocol (`visitors/base.py`)

```python
from typing import Protocol, TypeVar, runtime_checkable

T_co = TypeVar("T_co", covariant=True)

@runtime_checkable
class BacktestVisitor(Protocol[T_co]):
    name: str                  # key under which the composer stores the result
    def visit(self, report: BacktestReport) -> T_co: ...
```

`runtime_checkable` so `isinstance(v, BacktestVisitor)` works in the
composer. Generic over return type — different metrics return different
types (`Decimal` vs `Decimal | None` etc.).

## Concrete visitors (one per file)

### `SharpeRatioVisitor` → `Decimal`

- Inputs: `equity_curve` must have ≥ 2 points; otherwise returns `Decimal(0)`.
- Computes period-returns `r_t = (equity_t - equity_{t-1}) / equity_{t-1}`.
- Annualisation factor is configurable (default `Decimal("365")` for daily
  crypto), injected via constructor.
- Formula: `mean(r) / stdev(r) * sqrt(annualisation_factor)`.
- Risk-free rate: `Decimal(0)` default; overridable.
- Returns `Decimal` (negative values allowed).

### `MaxDrawdownVisitor` → `Decimal`

- Inputs: non-empty `equity_curve`.
- Single pass: track running peak, compute `(peak - equity) / peak` at each
  point, return the max. Empty curve → `Decimal(0)`.
- Result in the range `[0, 1]` (1 = total loss).

### `WinRateVisitor` → `Decimal`

- Inputs: `trades`.
- `sum(1 for t in trades if t.pnl > 0) / len(trades)`, with `0` when empty.
- Result in `[0, 1]`.

### `ProfitFactorVisitor` → `Decimal | None`

- `sum(pnl > 0) / abs(sum(pnl < 0))`.
- Returns `None` when gross loss is zero (all-winning portfolio — ratio
  undefined). Callers surface this explicitly instead of silently
  returning `inf`.

### `TotalReturnVisitor` → `Decimal`

- `(final_equity - initial_equity) / initial_equity`. Requires
  `initial_equity > 0` (validated in `BacktestReport.__post_init__`).

## Composer (`analytics_service.py`)

```python
class BacktestAnalyticsService:
    def __init__(self, visitors: Sequence[BacktestVisitor[Any]]) -> None:
        self._visitors = tuple(visitors)

    def run_all(self, report: BacktestReport) -> dict[str, Any]:
        return {v.name: v.visit(report) for v in self._visitors}
```

- No progress reporting, no Context — pure domain computation.
- Exceptions from visitors propagate (caller decides whether to wrap).
  Rationale: silent-failure-hunter findings from PR #1 pushed the project
  toward explicit failure; analytics should not hide a bad visitor.

## Testing strategy

Uses TDD (`superpowers:test-driven-development` skill). Per visitor:

1. A canonical fixture (equity curve + trade list with known expected
   result) — the arithmetic ground truth.
2. An edge-case fixture (empty curve, single trade, all-losing, etc.).
3. For `SharpeRatioVisitor` and `MaxDrawdownVisitor`: `hypothesis`
   property-based tests:
   - Max drawdown is in `[0, 1]` for any monotonic-increasing curve
     (= 0) and any monotonic-decreasing curve (= 1).
   - Sharpe of a constant equity curve is `0` (stdev denominator).
   - Annualisation factor scales Sharpe linearly by `sqrt(factor)`.

Test count target: ~25 unit tests for 2C (5 visitors × ~4 cases + 5
composer tests).

## Interface contract for 2B (future)

The `BacktestEngine` in 2B populates `BacktestReport`. For 2C we add a
`tests/unit/application/analytics/fixtures.py` module with a handful of
hand-built reports so analytics can be verified without 2B. When 2B lands,
its integration test will construct a report and feed it through
`BacktestAnalyticsService.run_all` as a smoke.

## Patterns touched

- **Visitor** (new, #15 in the shipped patterns list) — separates metric
  computation from `BacktestReport` traversal. Adds a metric without
  touching existing visitors or the report type.
- **Strategy** (already shipped in `MarketAnalyzer`) — `BacktestVisitor`
  protocol mirrors the `AnalysisStrategy` family: same shape, different
  input types.

## Open questions (deferred, not blockers)

1. Should `SharpeRatioVisitor` support sub-daily annualisation (8h / 4h
   equity snapshots)? Phase 2B will decide the equity-curve granularity.
2. `ProfitFactorVisitor` — some desks prefer MAR (return / |drawdown|)
   instead. Add as separate visitor in Phase 2+ if requested.
3. Sortino ratio — downside-deviation variant of Sharpe. Not in MVP
   scope; trivial to add as a 6th visitor later.

## Acceptance for 2C

- All modules listed under Architecture exist and pass type-checks.
- ≥ 25 unit tests covering happy path + edge cases, hypothesis for
  Sharpe / MaxDrawdown.
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src`
  all pass.
- No regressions — total suite remains 473 + 2C additions.
- Short entry in `CHANGELOG.md` under `[Unreleased]` describing 2C.
