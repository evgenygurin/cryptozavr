# Scalping Infrastructure — Roadmap

**Date:** 2026-04-22
**Status:** High-level roadmap, individual phases have their own specs.
**Drives:** 0.4.0+ of the plugin.

## Why this exists

The first live session (10 paper trades against KuCoin WebSocket) proved the
real-time infrastructure — `watch_position` + `wait_for_event` wake the LLM
with sub-second latency. It also exposed that the *strategy* side is
primitive: 0/10 `take_hit`, long counter-trend trades auto-die, and
all-or-nothing exits skew the distribution. The numbers show negative
expectancy before a single commission is paid.

This roadmap captures what we know needs to happen and in what order. Each
phase below gets its own spec + plan + implementation cycle.

## Principles

- **Ship the cheapest learning first.** Phase A turns ad-hoc bash ledgers
  into queryable data. Phase B tunes the thing with the largest PnL lever.
  Everything else is deferred until those two land and produce signal.
- **Validate in isolation.** Each phase has a well-defined interface and
  tests. No skipping layers.
- **DB as source of truth.** Paper trades go to Supabase; analysis reads
  from Supabase; stats are SQL views, not Python aggregations.
- **YAGNI.** Options, multi-user, account segregation, fees, funding,
  slippage — all deferred. We can add them when the data says we need to.

## Phases

### Phase 0 — MCP Stability Under Parallel Calls (new, urgent)

Live session reported that ~4 out of 8 tool calls dispatched in a single
parallel batch returned `"Connection closed"`, causing the MCP
subprocess to exit and requiring `/mcp` reconnect. Until this is fixed,
every phase below is fragile under real-world usage patterns where the
LLM wants to fan out (basket mode, parallel analyze_snapshot, multi-
symbol trending, etc.).

Hypotheses to investigate, in order of likelihood:

1. **asyncpg pool exhaustion** — default pool size might be saturated by
   concurrent calls holding connections during cache writes. Fix: size
   the pool explicitly, add `acquire_timeout`.
2. **ccxt rate-limit bursts** — parallel `get_ticker(force_refresh=True)`
   across venues could trigger exchange-side 429 → unhandled exception
   → crash. Fix: verify `RateLimitDecorator` covers every call path.
3. **Supabase Realtime subscriber races** — `cache_invalidator` may
   fight the cache-writer on the same key. Fix: verify single-writer
   invariant.
4. **FastMCP lifespan context race** — simultaneous tools mutating
   `watch_registry` or similar lifespan-held objects without locks.
   Fix: audit mutation sites, add asyncio locks where warranted.

**Exit criterion:** 20 parallel tool calls land in <2s with 0 connection
failures for at least 30 consecutive minutes of soak test.

**Why zero:** All subsequent phases assume the MCP server stays up under
normal load. Ignoring this burns every paper session the moment the LLM
does interesting parallel work.

### Phase A — Paper Trading Ledger (spec written, impl pending)

Spec: `2026-04-22-paper-trading-ledger-design.md`.

Adds `cryptozavr.paper_trades` table, `PaperLedgerService`, five MCP
tools, four resources, three prompts. `paper_open_trade` auto-starts a
`watch_position`; a terminal event auto-closes the trade through a
callback. Resume-on-startup recovers running trades. Joins the existing
`supabase_realtime` publication so multi-session and external dashboards
can react without polling.

**Exit criterion:** The LLM no longer touches `/tmp/scalp_ledger.jsonl`
or wraps `watch_position` in Bash scripts. It calls `paper_open_trade` /
`paper_close_trade`, reads `cryptozavr://paper/stats`, follows the
`discretionary_watch_loop` prompt.

**Why first:** Everything else needs structured trade data to measure
against. Also removes the ugliest user-facing friction.

### Phase B — Advanced Exits (trailing stop + partial take + trend filter)

New spec. Three independent mechanisms, one release.

1. **Trailing stop.** Three modes, user picks one per trade (default
   `fixed_pct`):
   - `fixed_pct(trail_pct)` — stop = highest/lowest × (1 ∓ trail_pct).
   - `atr_chandelier(period=14, multiplier=3)` — stop = HH/LL ∓ ATR × mult.
     Requires the existing `volatility_regime` analytics to expose ATR
     through a small helper.
   - `swing(period=20)` — stop = recent HH/LL swing level.
   Implementation: extends `WatchState` with `trail_mode`, `trail_params`,
   `trail_armed_at_pnl` (only start trailing after reaching some profit
   floor). `PositionWatcher._run` recomputes stop on each tick; the real
   stop-hit check uses the trailing level.

2. **Partial take.** `paper_open_trade` accepts `partial_takes: list[{
   trigger: Decimal, close_fraction: Decimal }]` (e.g. `[{trigger: "0.5R",
   close_fraction: 0.5}]`). New `WatchState.size_remaining`; a fill at a
   trigger records a synthetic close event with partial pnl, updates
   `size_remaining`, and keeps the position open with the balance. The
   `paper_trades` row gets child `paper_trade_fills` rows (new table).

3. **Trend filter at entry.** `paper_open_trade` has `allow_counter_trend:
   bool = false`. When `false`, open fetches the latest `analyze_snapshot`
   for the symbol and rejects trades where:
   - `side=long` and current price is below VWAP by > 0.3%, OR
   - `side=short` and current price is above VWAP by > 0.3%,
   - AND the `volatility_regime` flags "trending" (not "range").
   Returns a structured `rejection_reason` so the LLM sees why.

**Exit criterion:** Paper sessions show `take_hit_or_partial_filled > 0`
on the majority of non-stopped trades, and long counter-trend trades are
blocked by default.

**Why second:** This is the only phase that moves expectancy
directly. Phase A makes the measurement possible.

### Phase C — Portfolio Basket Mode (deferred until B validates)

`paper_open_basket(symbols: list[str], side: str, size_quote_per_trade:
Decimal, ...)`. Opens N simultaneous watches and — in `first_fire` mode —
cancels the rest the moment any one hits take or stop. Or `race` mode
where each survives independently.

Deferred because: without fixed exits it's mostly noise amplification.
Once Phase B gives the system a coherent exit story, basket mode
accelerates signal accumulation.

### Phase D — Strategy DSL + Forward Test (deferred)

Phase 2D of the project already has a declarative `StrategySpec` +
backtest engine. A new MCP tool `forward_test_strategy(spec_id)` runs
the same `StrategySpec` against live data via `watch_position`, writing
results into `paper_trades` with `strategy_spec_id` set. Side-by-side
`backtest vs forward` statistical comparison exposes overfit.

Deferred because: we need Phase B-era strategies worth comparing first.

### Phase E — Fees, Funding, Slippage

Simulation layer on top of pnl_quote. `TAKER_FEE_BPS` + `FUNDING_BPS_PER_8H`
applied at close time. Slippage modeled as order-book-depth-aware cost
using the existing `get_order_book` tool.

Deferred because: on paper trading sizes ($2.5k), the correction is a
handful of basis points — below the noise of exit-strategy problems we
haven't solved yet.

## Decision log

- **Why Phase C folds trend-filter?** Original plan made it Phase C
  standalone. It's ~60 lines (a filter function + one tool parameter),
  not worth a separate spec+plan cycle.
- **Why not SQLite instead of Supabase?** Project already has
  `asyncpg` + RLS + Realtime + migrations. One more table, no new deps.
- **Why not `task=True` for `watch_position`?** Already explored in the
  position-watcher spec — Claude Code's support is unverified, standard
  tools + `wait_for_event` long-poll are strictly more portable and
  work today.
- **Why `forward_test_strategy` and not "just use the backtest engine"?**
  Backtest runs on recorded OHLCV. Forward-test runs on live WS. Same
  strategy, different data source — the gap between them is where
  overfit lives.

## Acceptance for the whole roadmap

- Phase A + B shipped → paper sessions produce >50 trades per day with
  structured data in Supabase, `take_hit_or_partial_filled` > `stop_hit`
  on average days, trend-filter rejections logged as structured reasons.
- Phases C, D, E are optional upgrades gated on signals from A+B data.

## Next step

Invoke `writing-plans` against `2026-04-22-paper-trading-ledger-design.md`
to build the Phase A implementation plan. Phase B gets its own
brainstorm cycle once Phase A lands and we have real data to target.
