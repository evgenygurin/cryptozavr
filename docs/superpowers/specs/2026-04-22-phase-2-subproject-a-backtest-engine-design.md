# Phase 2 — Sub-project A — BacktestEngine (design)

> **Status:** APPROVED by user (2026-04-22, hybrid architecture, 6 MVP
> indicators, pandas dep, worst-case-first TP/SL, single-position).
> First of four Phase 2 sub-projects. Sequence: **A → (C ‖ B) → D**.

## Goal

Execute a `StrategySpec` (from 2A) against a historical OHLCV candle
series and produce a `BacktestReport` (from 2C). Deterministic,
testable in isolation, fee/slippage-aware.

## Non-goals

- **Multi-symbol / portfolio.** Single-position only. Portfolio belongs
  to Phase 4+.
- **Walk-forward / cross-validation.** Deferred.
- **Partial fills / live execution.** Phase 5.
- **MCP surface.** Sub-project B (next).
- **Persistence of BacktestReport.** Sub-project C.
- **Funding rates / perp mechanics.** Spot only; perps via a later fee
  model extension.
- **Indicator parameter extension.** Only the 6 `IndicatorKind`
  members from 2A (SMA/EMA/RSI/MACD/ATR/VOLUME). Adding BBANDS/ADX
  requires a DSL bump in a future 2A+1.

## Architecture — hybrid

Indicators are computed **vectorized** (one pass per `IndicatorRef` over
the full series). Trade lifecycle runs **streaming** bar-by-bar because
positions, TP, SL, and fees are event-driven and can't be vectorized
without losing intent clarity. The same streaming trade core can be
reused in Phase 4 live-signal work.

```text
src/cryptozavr/application/backtest/
├── __init__.py
├── indicators/
│   ├── __init__.py
│   ├── base.py          # Indicator Protocol
│   ├── price.py         # PriceSource extractor (Decimal-exact HLC3)
│   ├── sma.py
│   ├── ema.py
│   ├── rsi.py
│   ├── macd.py          # line only (signal + histogram deferred)
│   ├── atr.py
│   ├── volume.py
│   └── factory.py       # IndicatorRef → computed pd.Series[Decimal]
├── evaluator/
│   ├── __init__.py
│   ├── condition.py     # evaluate_condition(cond, series_map, bar_index)
│   └── strategy_evaluator.py
├── simulator/
│   ├── __init__.py
│   ├── slippage.py      # SlippageModel Protocol + PctSlippageModel
│   ├── fees.py          # FeeModel Protocol + FixedBpsFeeModel
│   ├── position.py      # OpenPosition (frozen dataclass)
│   └── trade_simulator.py
└── engine.py            # BacktestEngine.run(...) facade
```

Mirror test layout at `tests/unit/application/backtest/`.

## Indicator Protocol

```python
class Indicator(Protocol):
    @property
    def period(self) -> int: ...

    def compute(self, df: pd.DataFrame) -> pd.Series:
        """Return a pandas Series aligned to df.index, values are Decimal
        (or NaN during warm-up bars). One pass — no incremental state."""
```

Vectorised implementations use `numpy` arrays converted back to `Decimal`
at the boundary (keeps Decimal-exact money math but lets computation
run fast on float64). The `Decimal ↔ float64` conversion is the one
documented precision trade-off; tests assert match-within-tolerance
against hand-computed references for a 50-bar series.

### MVP indicators — locked formulas

Each formula below is the authoritative contract; tests pin numeric
ground truth against hand-computed references.

**SMA(period, source):** `mean(source[t-period+1 : t+1])`. Warm after
`period` bars. NaN before.

**EMA(period, source):** SMA of first `period` bars as seed, then
`EMA_t = alpha * source_t + (1 - alpha) * EMA_{t-1}` with
`alpha = 2 / (period + 1)`. Warm after `period` bars.

**RSI(period, source):** Wilder smoothing.
`gain_t = max(source_t - source_{t-1}, 0)`,
`loss_t = max(source_{t-1} - source_t, 0)`.
First warm bar (index `period`): `avg_gain = mean(gain_{1..period})`,
`avg_loss = mean(loss_{1..period})`. Afterwards:
`avg_gain_t = (avg_gain_{t-1} * (period - 1) + gain_t) / period`
(same for loss). Output:
`RS = avg_gain / avg_loss`, `RSI = 100 - 100 / (1 + RS)`.
Edge: `avg_loss == 0` ⇒ `RSI = 100` (max-bullish convention).
Warm after `period + 1` bars.

**MACD(slow, source):** fast=12, signal=9 hard-coded in MVP. Output =
`EMA(fast) - EMA(slow)` (line only — signal and histogram exposed in a
later DSL bump). Warm after `slow` bars.

**ATR(period):** OHLC-only (ignores `PriceSource`). True range:
`TR_t = max(high_t - low_t, |high_t - close_{t-1}|,
|low_t - close_{t-1}|)`. Seed: `mean(TR_{1..period})`. Wilder smoothing
afterwards. Warm after `period + 1` bars.

**Volume:** identity on `candle.volume`. Warm after bar 0.

### `IndicatorFactory`

Returns one `pd.Series[Decimal]` per unique `IndicatorRef` in the spec.
Interning: a spec that references the same `IndicatorRef` in entry +
exit triggers a single compute call. Same-`(kind, period, source)`
comparison already works (Pydantic frozen model, `__hash__` derived).

## Evaluator

Stream-like but backed by pre-computed Series:

```python
def evaluate_condition(
    condition: Condition,
    series: dict[IndicatorRef, pd.Series],
    bar_index: int,
) -> bool | None:
    ...  # read series[ref].iloc[bar_index] + iloc[bar_index-1] for crossings
```

Same 6-op semantics as the revert-documented evaluator
(GT/GTE/LT/LTE/CROSSES_ABOVE/CROSSES_BELOW), with `None`-propagation on
warm-up (`NaN`) or missing previous value (`bar_index == 0`).

`StrategyEvaluator.tick(bar_index) → SignalTick(entry, exit)` folds
entry conditions as **AND** and exit conditions as **OR**, returning
`None` on any unresolved condition.

## Simulator

### Models

```python
class SlippageModel(Protocol):
    def adjust(
        self, *, reference: Decimal, side: StrategySide, is_entry: bool
    ) -> Decimal: ...

class FeeModel(Protocol):
    def compute(self, *, notional: Decimal, is_entry: bool) -> Decimal: ...
```

**Defaults in MVP:** `PctSlippageModel(bps=10)` and
`FixedBpsFeeModel(bps=5)`. Zero-bps constructors valid (friction-free
mode for analytics sanity checks); negative bps rejected at
construction.

### OpenPosition (frozen)

```python
@dataclass(frozen=True, slots=True)
class OpenPosition:
    side: StrategySide
    entry_price: Decimal          # slippage-adjusted fill
    size: Decimal                 # base-currency qty
    entry_bar_index: int
    take_profit_level: Decimal | None   # absolute price, precomputed
    stop_loss_level: Decimal | None
```

### Per-bar rule

```text
tick(candle, signal):
  if no position and signal.entry == True:
    open (fill = slippage.adjust(close, side, is_entry=True);
          size = equity * size_pct / fill;
          if size == 0: skip with log; return)
    charge entry fee (debited from equity)
  elif open position:
    # Intrabar TP/SL check BEFORE exit signal — even on an exit bar
    # the TP/SL may have hit first.
    if TP and SL both inside [candle.low, candle.high]:
      # Worst-case-first: SL wins for LONG, TP wins for SHORT.
      close at SL level (LONG) / TP level (SHORT), minus slippage, minus fee
    elif SL inside:   close at SL
    elif TP inside:   close at TP
    elif signal.exit == True:
      close at close price (with slippage + fee)
    else:
      mark-to-market at candle.close
  always append EquityPoint for this bar
```

### Equity curve length invariant

`len(equity_curve) == len(candles)` — one point per input bar. Makes
sub-project B's analytics tools pair candles and equity trivially and
keeps 2C visitors drop-in.

### Dust trades

Two-level check at entry time:

1. `size == 0` (sizing rounded to zero given Decimal precision) → skip.
2. `size * entry_price < min_notional` (if configured) → skip.

`min_notional: Decimal | None` is an optional constructor parameter on
`TradeSimulator`; default `None` = no check. Real venues reject orders
below a notional floor (Binance spot = 10 USDT, KuCoin varies); this
field mirrors the CCXT `market.limits.cost.min` value so callers that
care about venue realism can opt in. Backtest tests default to `None`
for determinism; E2E tests that exercise realism pass an explicit value.

On skip: emit `logging.WARNING` with the spec name + bar index + reason,
do not advance to an open position. Equity point is still appended for
this bar.

## Engine facade

```python
class BacktestEngine:
    def run(
        self,
        spec: StrategySpec,
        candles: pd.DataFrame,
        *,
        initial_equity: Decimal,
        slippage: SlippageModel | None = None,
        fees: FeeModel | None = None,
        min_notional: Decimal | None = None,
    ) -> BacktestReport: ...
```

Steps:
1. Validate DataFrame shape (required columns, sorted by time, no NaN
   in OHLCV). Raise `ValidationError` on malformed input.
2. `IndicatorFactory.compute_all(spec, df) → series_map`.
3. Construct `StrategyEvaluator(series_map)` + `TradeSimulator(spec,
   initial_equity, slippage, fees)`.
4. Per-bar loop: `evaluator.tick → simulator.tick → append equity`.
5. At end, if a position is still open, close it at the final
   `close` price (with slippage + fee).
6. Pack `BacktestReport(trades, equity_curve, initial_equity,
   final_equity, period, strategy_name)` and return.

## Edge cases (locked behaviour)

| Case | Behaviour |
|---|---|
| Empty candles | `ValidationError` (can't backtest zero bars) |
| Single candle | Valid input, produces 1 equity point, no trades (no crossings possible) |
| Warm-up bars with NaN indicators | `signal is None` → simulator stays flat, equity point = `initial_equity` |
| Entry signal on bar 0 of warm-up | Ignored (signal is None during warm-up by construction) |
| Position open at series end | Close at last `close` with slippage + fee |
| `size_pct × equity / fill_price == 0` (dust) | Skip entry, WARNING log |
| `size × fill_price < min_notional` (if configured) | Skip entry, WARNING log with reason="below_min_notional" |
| `equity` goes negative | Allowed — `BacktestReport` doesn't reject it, 2C `MaxDrawdownVisitor` already clamps |
| Exit bar with both TP and SL inside range | Worst-case-first (SL/LONG, TP/SHORT) |
| Fees > realized gross | Trade still emitted with negative pnl (consistent sign) |

## Testing strategy

Target **≥80 unit tests + ≥10 E2E** (sweep goes 555 → ~645).

Breakdown:

- **Indicators (~35):** each of 6 indicators × 5-7 cases (warm-up,
  hand-computed reference on 50 bars, edge case, property test for
  bounded series, factory returns correct type). Match-within-tolerance
  against hand-computed numpy truth.
- **Evaluator (~15):** 6 comparator ops × (true/false/warm-up/None),
  AND/OR-fold edge cases, same-ref sharing.
- **Simulator (~20):** each of {entry, exit-signal, TP-hit, SL-hit,
  both-inside-worst-case, dust-skip, min-notional-skip, fees-reduce-pnl,
  pnl-sign-LONG, pnl-sign-SHORT, multiple-trades, ends-with-open-position}.
- **Engine E2E (~10):** synthetic trending series + realistic spec →
  assert positive PnL, asserted trade count, 2C visitors happy;
  mean-reversion spec on choppy series; empty-candles rejection;
  position-still-open-at-end closes cleanly; malformed df rejected.

Property tests (hypothesis): random bounded candles + any legal spec
never raise, `BacktestReport` always valid, 2C visitors always return
`Decimal | None` (never NaN / inf / exception).

## Dependencies

**Add:** `pandas>=2.2`. (numpy already transitive via CCXT.) No
`ta-lib` / `pandas-ta` — 6 native-numpy indicators keep CI light and
pinnable.

**Existing, reused:** pydantic, Decimal, 2A (`StrategySpec` +
`IndicatorRef`), 2C (`BacktestReport` + visitors).

## Future extensions (deferred — design-level compatibility notes)

The `SlippageModel` and `FeeModel` Protocols are explicit so the
following drop-in replacements can land later without touching
`TradeSimulator` internals:

- **`MarketDrivenFeeModel(ccxt_market: dict)`** — reads
  `market.maker` / `market.taker` / `market.percentage` /
  `market.feeSide` from a CCXT `exchange.markets[symbol]` dict and
  computes venue-realistic fees. Spot-only assumes `feeSide == 'quote'`;
  perp/inverse paths wait until Phase 4+ perp work.
- **`SpreadSlippageModel(order_book_depth: OrderBookSnapshot)`** —
  walks the CCXT order book instead of applying a flat bps to the
  close price. Useful for large-notional backtests where bps-flat
  understates impact.
- **Per-venue `min_notional` auto-population** — if a backtest run is
  scoped to a specific `VenueId + Symbol`, populate `min_notional` from
  `market.limits.cost.min` automatically instead of taking it as a
  constructor argument.

None of these require changes to 2A (`StrategySpec`) or 2C
(`BacktestReport`); they extend the simulator surface only.

## Acceptance

1. All modules in the Architecture section exist + pass type-check.
2. `uv run pytest tests/unit tests/contract -m "not integration" -q`
   green; sweep grew from 555 to ≈645 (≥80 unit + ≥10 E2E new).
3. `uv run ruff check .` + `ruff format --check .` + `mypy src` green.
4. CHANGELOG `[Unreleased]` entry describing sub-project A and locking
   the dependency bump (pandas).
5. `BacktestEngine.run` produces a `BacktestReport` that the 2C
   `BacktestAnalyticsService` runs through all 5 visitors without error
   on both trending and choppy synthetic series (smoke test in E2E).

## Open items — none

All previously-open questions are resolved by the brainstorming
approval (hybrid architecture, 6 MVP indicators, pandas dep,
worst-case-first TP/SL, single-position, no ta-lib). Nothing left to
arbitrate — implementation plan goes next.
