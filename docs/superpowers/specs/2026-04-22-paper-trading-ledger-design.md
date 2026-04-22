# Paper Trading Ledger — Design

**Date:** 2026-04-22
**Status:** Design approved, pending implementation plan
**Depends on:** `2026-04-22-position-watcher-design.md` (Position Watcher)

## Problem

The Position Watcher feature lets an LLM track a live position via WebSocket
and react to events. In practice, the LLM has been wrapping that primitive
with ad-hoc Bash scripts — writing each open/close to `/tmp/scalp_ledger.jsonl`
and recomputing stats inline with `python3 -c "..."` pipes. This is fragile,
non-reusable across sessions, loses state on server restart, and offers no
structured view of the account.

## Goals

- Paper trading is a first-class feature of the plugin, not an LLM hack.
- Trades are persisted in Supabase and survive server restarts.
- Opening a trade automatically starts a Position Watcher; a terminal event
  automatically closes the trade.
- Bankroll, open trades, closed trades, and running stats are exposed as
  MCP resources so the LLM can cite them instead of grepping files.
- Prompts encode disciplined scalping + review workflows.

## Non-goals

- Real exchange order placement — this is paper only.
- Multi-user / multi-account — a single global ledger per Supabase database.
- Multi-strategy comparison — one bankroll, one stream of trades. A user
  who wants segregation can use `paper_reset` between sessions.
- Fractional P&L, slippage, fees — v1 uses nominal entry/exit × size. Fees
  and slippage can be layered later.

## Architecture

Three layers matching the existing project pattern:

```text
┌────────────────────────────────────────────────────────────────┐
│ L5 MCP — src/cryptozavr/mcp/{tools,resources,prompts}/paper.py │
│  tools:     paper_open_trade, paper_close_trade,               │
│             paper_cancel_trade, paper_reset, paper_set_bankroll│
│  resources: cryptozavr://paper/ledger                          │
│             cryptozavr://paper/open_trades                     │
│             cryptozavr://paper/stats                           │
│             cryptozavr://paper/trades/{trade_id}               │
│  prompts:   paper_scalp_session, paper_review                  │
│             discretionary_watch_loop                           │
└─────────────────────────────┬──────────────────────────────────┘
                              │
┌─────────────────────────────▼──────────────────────────────────┐
│ L4 Application — PaperLedgerService                            │
│  - open_trade(side, symbol, entry, stop, take, size) -> id     │
│  - close_trade(id, exit_price, reason) -> Trade                │
│  - cancel_trade(id) -> Trade                                   │
│  - list_open() / list_all(limit, offset) / stats() -> ...      │
│  - resume_open_watches() — invoked from lifespan at startup    │
│  - _on_watch_terminal(trade_id, event) — registered callback   │
└─────────────────────────────┬──────────────────────────────────┘
                              │
┌─────────────────────────────▼──────────────────────────────────┐
│ L2 Infra — PaperTradeRepository (asyncpg)                      │
│  - insert(row) -> trade_id                                     │
│  - set_watch_id(trade_id, watch_id)                            │
│  - close(trade_id, exit, closed_at, pnl, reason) -> rowcount   │
│  - fetch_by_id / fetch_open / fetch_page                       │
│  - stats() -> PaperStatsRow                                    │
└────────────────────────────────────────────────────────────────┘
```

The existing `PositionWatcher` gains one optional parameter in its `start()`
method: `on_terminal: Callable[[str, WatchEvent], Awaitable[None]]`. The
callback fires exactly once when the watch loop transitions to a terminal
state (`stop_hit` / `take_hit` / `timeout`). `PaperLedgerService` registers
this callback so the trade is closed atomically when the watcher fires.

## Data layer

### Migration: `supabase/migrations/00000000000090_paper_trades.sql`

```sql
create table cryptozavr.paper_trades (
  id              uuid primary key default gen_random_uuid(),
  side            text not null check (side in ('long', 'short')),
  venue           text not null,
  symbol_native   text not null,
  entry           numeric(20, 8) not null check (entry > 0),
  stop            numeric(20, 8) not null check (stop > 0),
  take            numeric(20, 8) not null check (take > 0),
  size_quote      numeric(20, 8) not null check (size_quote > 0),
  opened_at_ms    bigint not null,
  max_duration_sec integer not null,
  status          text not null check (status in ('running', 'closed', 'abandoned')),
  exit_price      numeric(20, 8),
  closed_at_ms    bigint,
  pnl_quote       numeric(20, 8),
  reason          text,     -- stop_hit|take_hit|timeout|manual_cancel|abandoned|error
  watch_id        text,     -- current live watch id (null if not watched)
  note            text
);

create index paper_trades_status
  on cryptozavr.paper_trades (status)
  where status = 'running';

create index paper_trades_opened_desc
  on cryptozavr.paper_trades (opened_at_ms desc);

create index paper_trades_watch_id
  on cryptozavr.paper_trades (watch_id)
  where watch_id is not null;

alter table cryptozavr.paper_trades enable row level security;

create policy service_role_all on cryptozavr.paper_trades
  for all to service_role using (true) with check (true);

-- View: running stats (computed on demand, not cached).
create or replace view cryptozavr.paper_stats as
select
  count(*) filter (where status = 'closed')                     as trades_count,
  count(*) filter (where status = 'closed' and pnl_quote > 0)   as wins,
  count(*) filter (where status = 'closed' and pnl_quote <= 0)  as losses,
  count(*) filter (where status = 'running')                    as open_count,
  coalesce(sum(pnl_quote) filter (where status = 'closed'), 0)  as net_pnl_quote,
  coalesce(avg(pnl_quote) filter (where status = 'closed' and pnl_quote > 0), 0)
    as avg_win_quote,
  coalesce(avg(pnl_quote) filter (where status = 'closed' and pnl_quote <= 0), 0)
    as avg_loss_quote
from cryptozavr.paper_trades;
```

### P&L computation

```text
long:  pnl = (exit - entry) * (size_quote / entry)
short: pnl = (entry - exit) * (size_quote / entry)
```

`size_quote` is measured in USDT; `entry`/`exit` are prices. The division
gives the base-unit quantity implied by the quote size. This keeps the
math simple and lets the user think in "I risked $2,500".

### Bankroll

Stored outside the table — single numeric constant controlled by the
`CRYPTOZAVR_PAPER_BANKROLL` env var (default `10000`). The live bankroll
is `CRYPTOZAVR_PAPER_BANKROLL + net_pnl_quote` (from the `paper_stats`
view). `paper_set_bankroll` updates a process-local override in the
lifespan dict; it does **not** touch env vars or config files. Resetting
the ledger restores the env default.

## MCP tools

### `paper_open_trade`

```sql
Input:
  venue: str (default "kucoin")
  symbol: str
  side: "long" | "short"
  entry: Decimal
  stop: Decimal
  take: Decimal
  size_quote: Decimal
  max_duration_sec: int = 3600
  note: str | None = None

Behaviour:
  1. Resolve symbol.
  2. Validate prices (reuse WatchState invariants).
  3. INSERT row with status='running', watch_id=null.
  4. watcher.start(..., on_terminal=_close_on_terminal(trade_id))
     returns watch_id.
  5. UPDATE SET watch_id = $watch_id WHERE id = $trade_id.
  6. Return PaperTradeDTO.

Returns: PaperTradeDTO (see below).
```

### `paper_close_trade`

```bash
Input:
  trade_id: str (uuid)
  exit_price: Decimal
  reason: str = "manual_cancel"   -- free-form label

Behaviour:
  1. SELECT row; if not found -> error; if closed -> idempotent no-op,
     return current snapshot.
  2. If watch_id is set -> watcher.stop(watch_id) (best-effort, ignore
     WatchNotFoundError — the watch may have already terminated).
  3. Atomic UPDATE ... WHERE id = $trade_id AND status = 'running'.
     If 0 rows updated (race with terminal callback) — fetch and return
     current state; that's the truth.

Returns: PaperTradeDTO
```

### `paper_cancel_trade`

Thin wrapper around `paper_close_trade` with `reason="manual_cancel"` and
`exit_price` fetched from a fresh ticker (`get_ticker(force_refresh=True)`)
so the LLM doesn't have to supply it.

### `paper_reset`

```text
Input:
  confirm: str  -- must equal "RESET"

Behaviour:
  1. If confirm != "RESET" -> ValidationError.
  2. For every open trade: best-effort watcher.stop(watch_id).
  3. TRUNCATE cryptozavr.paper_trades.
  4. Clear the lifespan bankroll override.

Returns: {"trades_deleted": int, "bankroll": Decimal}
```

### `paper_set_bankroll`

```bash
Input:
  bankroll: Decimal (> 0)

Behaviour:
  1. Update process-local override in lifespan dict.
  2. Return the new live bankroll (override + net_pnl_quote).
```

## MCP resources

All resources return structured JSON via `ResourceResult`.

### `cryptozavr://paper/ledger`

All trades, newest first, up to 200. For deeper history, `paper_trades/{id}`
or filters via future templated resources.

```json
{
  "trades": [PaperTradeDTO, ...],
  "total_count": int,
  "returned": int
}
```

### `cryptozavr://paper/open_trades`

Only `status='running'` rows, newest first. Intended for a quick "what do I
still have on" snapshot.

### `cryptozavr://paper/stats`

Snapshot of the `paper_stats` view plus bankroll:

```json
{
  "trades_count": 7,
  "wins": 3,
  "losses": 4,
  "win_rate": 0.4286,
  "net_pnl_quote": -4.06,
  "avg_win_quote": 2.63,
  "avg_loss_quote": -2.98,
  "open_count": 1,
  "bankroll_initial": 10000.00,
  "bankroll_live": 9995.94
}
```

### `cryptozavr://paper/trades/{trade_id}` (templated)

Full single-trade view including note, watch_id, raw timestamps. 404-style
error if unknown.

## MCP prompts

### `paper_scalp_session`

Multi-message template: system prompt pins the session rules (bankroll,
max trades, RR ≥ 1, no more than 25% of bankroll per trade, pause after 3
losses in a row), user prompt asks the model to begin. Reusable anchor that
keeps discipline across sessions.

### `paper_review`

Two-message template: system prompt instructs the model to read
`cryptozavr://paper/ledger` and `paper/stats`, extract patterns (bias,
winning conditions, losing conditions, psychological notes from the `note`
field). Output is a short post-session report.

### `discretionary_watch_loop`

Single-message template: tells the model to call `wait_for_event(trade_id)`
in a loop and, on each event, choose one of {move_stop_to_breakeven,
partial_close, close, hold}. This is the idiomatic runtime loop — the
Bash/sleep patterns the LLM was inventing get replaced by this single
prompt.

## Resume-on-startup

In `bootstrap.py`, after `PaperLedgerService` is constructed but before
`yield`:

```python
await paper_ledger.resume_open_watches()
```

`resume_open_watches` steps:
1. `SELECT * FROM paper_trades WHERE status = 'running'`.
2. For each row:
   a. `SymbolResolver.resolve(...)` the native symbol.
   b. `watcher.start(..., on_terminal=_close_on_terminal(id))`.
   c. `UPDATE SET watch_id = $new WHERE id = $trade_id`.
3. On failure for a specific row (symbol gone, venue down):
   `UPDATE SET status='abandoned', reason='resume_failed', closed_at_ms=now`.

The server will not start without a working DB — the existing `asyncpg`
pool is a hard dependency already, so this adds no new failure mode.

## Terminal-event callback

`PositionWatcher.start()` already runs the watch loop as a detached task.
The new `on_terminal` parameter attaches a callback invoked from `_run`
exactly once when `status` transitions to a terminal value. Contract:

- Invoked **after** the state mutation, **before** the task exits.
- Signature: `async def on_terminal(watch_id: str, event: WatchEvent) -> None`.
- Exceptions inside the callback are logged but do not propagate — the
  watcher's job is done; the ledger layer is responsible for its own
  retry logic if the DB write fails.

The ledger registers `functools.partial(self._on_watch_terminal, trade_id)`.
The handler:

1. Computes `pnl_quote` from the trade row and the event `price`.
2. Calls `repository.close(trade_id, exit=price, closed_at_ms, pnl, reason)`
   — the atomic UPDATE-WHERE-running.
3. On rowcount=0 — no-op (already closed through `paper_close_trade` race).
4. On DB error — retries 3x with 500ms / 2s / 8s backoff, then logs and
   gives up. The running watch is gone by now; the row stays `running`
   until the next restart resume, which will pick it up again and create
   a fresh watch. This is an acceptable degradation mode for paper trading.

## Error handling

| Error | Translation |
|---|---|
| Trade not found | `TradeNotFoundError` (new, extends `NotFoundError`) → `ToolError` |
| Invalid prices (long: stop >= entry etc.) | `ValidationError` → `ToolError` |
| `SymbolNotFoundError` at open | bubbles to tool, no row inserted |
| Watcher start fails after INSERT | mark trade `abandoned`, raise original |
| DB write fails on close | retry 3x with backoff, then log (`reason='close_retry_exhausted'`) |
| `paper_reset` without `confirm="RESET"` | `ValidationError` |

## Testing

**Unit (`tests/unit/application/services/test_paper_ledger_service.py`):**

- `open_trade` happy path with fake watcher + fake repo.
- `close_trade` idempotent: closing an already-closed trade returns current
  state, no extra UPDATE.
- `on_terminal` callback closes the trade with correct `pnl_quote` for both
  long and short sides.
- `resume_open_watches` starts fresh watches and records new `watch_id`.
- `resume_open_watches` marks `abandoned` on `SymbolNotFoundError`.

**Contract (`tests/contract/test_paper_trade_repo.py`):**

- Schema round-trip for one trade row (insert, set_watch_id, close).
- `stats()` view matches handwritten aggregate on a handful of rows.

**Integration (`tests/integration/test_paper_ledger_live.py`,
`@pytest.mark.integration`):**

- Real KuCoin WS + real Supabase: open trade → assert row inserted with
  running state → stop_watch → assert closed row with reason='manual_cancel'.
- Marked skipped under `SKIP_LIVE_TESTS=1` and `SKIP_SUPABASE_TESTS=1`
  (existing conventions).

## Performance

- `paper_open_trade`: 1 INSERT + 1 UPDATE + watcher.start (~100 ms total,
  dominated by INSERT round-trip).
- `paper_close_trade`: 1 SELECT + 1 UPDATE + 1 stop_watch (~100 ms).
- `cryptozavr://paper/ledger`: bounded at 200 rows, ~5 ms.
- `cryptozavr://paper/stats`: `paper_stats` view aggregates the whole
  table. For >100k rows we'd materialise it; for paper trading size, a
  single `SELECT` is fine.

## Open risks

1. **Clock skew** between server and Supabase. All timestamps use server
   wall-clock `int(time.time() * 1000)`; DB default `now()` is only for
   row `id` generation (uuid). Mitigation: rely on a single source
   (server) for all trade timestamps. Supabase defaults are not used for
   business timestamps.
2. **Duplicate watches after restart.** If a row has `watch_id` set but
   the server was restarted, the old `watch_id` is stale. Resume creates
   a *new* watch and overwrites `watch_id`. No real duplication because
   the old watch was torn down with the process.
3. **Abandoned trades accumulating.** `resume_open_watches` handles this,
   but if resume itself fails repeatedly (e.g. Supabase reachable but
   KuCoin refuses), rows stay `abandoned` with the failure reason. Not a
   correctness issue — the LLM sees the state in `paper/ledger`.

## Out of scope (future)

- Per-strategy / per-session segregation (`paper_sessions` table).
- Bankroll event log (`deposit`/`withdraw` history).
- Fees, funding, slippage models.
- Time-based stats (hourly / daily / by weekday).
- CSV / JSONL export tool.
- Partial closes (split a trade into two rows with shared parent).

## Implementation order (for plan)

1. `domain/paper.py` — `PaperSide`, `PaperStatus`, `PaperTrade` frozen
   dataclass, `PaperStats` dataclass. `TradeNotFoundError` in exceptions.
2. Migration: `00000000000090_paper_trades.sql` + `paper_stats` view.
3. L2 `PaperTradeRepository` — asyncpg CRUD + stats().
4. L4 `PaperLedgerService` — open/close/cancel/reset + `on_terminal`
   callback + `resume_open_watches`.
5. `PositionWatcher` — add `on_terminal` hook to `start()` / `_run()`.
6. Lifespan wiring: new keys `paper_ledger`, `paper_bankroll_override`.
7. MCP DTOs: `PaperTradeDTO`, `PaperStatsDTO`.
8. L5 MCP tools, resources, prompts.
9. Unit + contract + integration tests.
10. CHANGELOG + version bump 0.3.4 → 0.4.0 (new subsystem, minor bump).
