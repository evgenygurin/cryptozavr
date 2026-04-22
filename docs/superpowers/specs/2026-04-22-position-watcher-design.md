# Position Watcher — Real-Time Event-Driven Monitoring

**Date:** 2026-04-22
**Status:** Design approved, pending implementation plan

## Problem

When a user opens a paper-trading position, they need continuous monitoring
of price + volume + key levels so they can make discretionary decisions
(move stop to breakeven, partial exit, re-entry) without blocking the
conversation. REST polling (the current `get_ticker` approach) has a
minimum practical interval of ~1 minute via `/loop` — too slow for
scalping and wasteful for swing.

## Goals

- Real-time (tick-level) price awareness for any active position
- Non-blocking: user keeps working while watch runs
- Event stream surfaces discretionary-relevant moments, not just stop/take
- Works uniformly from scalp (minutes) to swing (hours)
- Compatible with any MCP client (not FastMCP-client-specific)

## Non-goals

- Executing actual trades (paper-only)
- Multi-exchange arbitrage
- News / external signal integration
- Persistence across server restarts (in-memory only — paper trading
  presumes fresh session)
- `volume_spike` and `level_broken` events — deferred to v2

## Architecture

### Principle

A `watch_position` tool returns immediately with a `watch_id`. The actual
monitoring runs as a detached `asyncio.Task` on the MCP server's event
loop, owned by the server's lifespan. The tool boundary (~100 ms) is
entirely decoupled from the watch lifetime (seconds to hours).

State lives in a mutable dict in `ctx.lifespan_context`. `check_watch`
reads it; `stop_watch` cancels the task and reads final state. No
FastMCP-specific `task=True` machinery, no `progressToken` dependency,
no cross-process Docket backend — just `asyncio.create_task` +
`asyncio.Task.cancel`.

### Why not `task=True`?

1. FastMCP's `task=True` protocol is consumed via the FastMCP *client*
   (`task.status()`, `task.cancel()`). Claude Code uses a generic MCP
   client — no guarantees it supports the task polling protocol.
2. `task=True` in-memory backend loses tasks on restart (same as our
   approach), but adds Docket dependency and extra surface area for
   zero benefit given Claude Code's unknown support.
3. Progress via `ctx.report_progress` requires client-side
   `progressToken` — also not guaranteed.

### Why not `ctx.info` event streaming?

FastMCP docs explicitly do not guarantee real-time delivery of
`ctx.info/warning/error` — timing is client-implementation-dependent.
Pulling events via `check_watch` polls (cheap, same-process dict read)
is deterministic and universally supported.

### Components

```text
┌──────────────────────────────────────────────────┐
│ L5 MCP tools (src/cryptozavr/mcp/tools/watch.py) │
│   watch_position, check_watch, stop_watch        │
└────────────────────┬─────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────┐
│ L4 Application                                    │
│   PositionWatcher  (services/position_watcher.py)│
│   EventDetector    (pure function)                │
│   WatchState       (domain/watch.py)              │
└────────────────────┬─────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────┐
│ L2 Infrastructure                                 │
│   KucoinWsProvider (providers/kucoin_ws.py)      │
│   wraps ccxt.pro.kucoin                           │
└──────────────────────────────────────────────────┘
```

### Lifespan wiring

Two new keys added to `lifespan_state.LIFESPAN_KEYS`:

- `ws_provider: KucoinWsProvider` — singleton, lazy-inits the
  `ccxt.pro.kucoin` instance on first `watch_ticker` call. One shared
  connection supports up to 100 subscriptions (KuCoin limit).
- `watch_registry: dict[str, WatchState]` — all live + terminated
  watches for the session.

On shutdown: cancel every running `WatchState._task`, `await` them
(swallowing `CancelledError`), then `await ws_provider.close()`.

## Data model

### `WatchSide` (enum)

- `long` | `short`

### `WatchStatus` (enum)

- `running` — actively watching
- `stop_hit` — terminal, price crossed stop
- `take_hit` — terminal, price crossed take
- `timeout` — terminal, `max_duration_sec` elapsed
- `cancelled` — terminal, user called `stop_watch`
- `error` — terminal, WS provider unrecoverable failure

### `WatchEvent` (frozen dataclass)

| Field | Type | Notes |
|---|---|---|
| `type` | `EventType` | Enum (below) |
| `ts_ms` | `int` | Unix ms when event fired |
| `price` | `Decimal` | Price at fire time |
| `details` | `dict[str, str]` | Event-specific context |

### `EventType` (enum)

| Type | Fire condition (long) | Fire condition (short) | Terminal? | Fire-once? |
|---|---|---|---|---|
| `price_approaches_stop` | `price ≤ stop × 1.005` | `price ≥ stop × 0.995` | no | yes |
| `price_approaches_take` | `price ≥ take × 0.995` | `price ≤ take × 1.005` | no | yes |
| `breakeven_reached` | `pnl ≥ 1R` (R = `entry - stop`) | `pnl ≥ 1R` (R = `stop - entry`) | no | yes |
| `stop_hit` | `price ≤ stop` | `price ≥ stop` | **yes** | one-shot |
| `take_hit` | `price ≥ take` | `price ≤ take` | **yes** | one-shot |
| `timeout` | `now_ms ≥ started_at_ms + max_duration*1000` | same | **yes** | one-shot |

Fire-once events use a set of already-fired types stored in
`WatchState._fired_non_terminal`.

### `WatchState` (mutable dataclass, lives in registry)

| Field | Type | Notes |
|---|---|---|
| `watch_id` | `str` | UUID hex, 12 chars |
| `venue` | `str` | Always `kucoin` in v1 |
| `symbol` | `Symbol` | Resolved via `SymbolResolver` |
| `side` | `WatchSide` | |
| `entry` | `Decimal` | User-declared entry price |
| `stop` | `Decimal` | |
| `take` | `Decimal` | |
| `size_quote` | `Decimal` \| None | Optional — if provided, P&L is in USD; if not, P&L is in %. |
| `started_at_ms` | `int` | |
| `max_duration_sec` | `int` | `60 ≤ x ≤ 86400`, default `3600` |
| `status` | `WatchStatus` | |
| `current_price` | `Decimal` \| None | Last tick seen |
| `last_tick_at_ms` | `int` \| None | For staleness diagnostics |
| `pnl_quote` | `Decimal` \| None | Absolute USD P&L if `size_quote` set |
| `pnl_pct` | `Decimal` \| None | Always computable |
| `events` | `list[WatchEvent]` | Ring buffer, bounded at 200 |
| `_fired_non_terminal` | `set[EventType]` | Implementation detail |
| `_task` | `asyncio.Task` \| None | Not serialised / not in DTO |

### Validation at creation

- `entry > 0`, `stop > 0`, `take > 0`
- For `long`: `stop < entry < take`
- For `short`: `take < entry < stop`
- `max_duration_sec` in `[60, 86400]`

Violations → `ValidationError` (domain exception) → translated to
MCP `ToolError` via existing `domain_to_tool_error`.

## MCP tools

### `watch_position`

```bash
Inputs:
  venue: str            (default "kucoin")
  symbol: str           (e.g. "BTC-USDT")
  side: "long" | "short"
  entry: Decimal
  stop: Decimal
  take: Decimal
  size_quote: Decimal | None  (optional — for USD P&L)
  max_duration_sec: int = 3600

Behaviour:
  1. Resolve symbol via existing SymbolResolver
  2. Validate prices (sides + ordering)
  3. Generate watch_id (UUID hex, 12 chars)
  4. Build WatchState; put in registry
  5. asyncio.create_task(_run_watch_loop(state, ws_provider))
  6. Return WatchIdDTO immediately

Returns:
  WatchIdDTO { watch_id, status, started_at_ms, expected_end_at_ms }

Tags: {"market", "position", "streaming"}
Annotations: readOnlyHint=False (creates server-side task), idempotentHint=False
```

### `check_watch`

```bash
Inputs:
  watch_id: str
  since_event_index: int = 0   (return events[since_event_index:])

Behaviour:
  1. Look up watch_id in registry; raise WatchNotFoundError if missing
  2. Build DTO snapshot from current WatchState

Returns:
  WatchStateDTO {
    watch_id, symbol, side, entry, stop, take,
    status, current_price, last_tick_at_ms,
    pnl_quote, pnl_pct, elapsed_sec,
    events: list[WatchEventDTO],   (slice from since_event_index)
    next_event_index: int,         (for next call's since_event_index)
  }

Tags: {"market", "position", "read-only"}
Annotations: readOnlyHint=True, idempotentHint=True
```

### `stop_watch`

```bash
Inputs:
  watch_id: str

Behaviour:
  1. Look up watch_id; raise WatchNotFoundError if missing
  2. If state.status == "running":
       state._task.cancel()
       await state._task  (suppress CancelledError)
       state.status = "cancelled"
  3. Return final snapshot (same as check_watch full)

Returns: WatchStateDTO

Tags: {"market", "position"}
Annotations: readOnlyHint=False, idempotentHint=True (stopping a stopped watch returns same snapshot)
```

## Provider layer

### `KucoinWsProvider`

```python
class KucoinWsProvider:
    def __init__(self) -> None:
        self._exchange: ccxt.pro.kucoin | None = None
        self._lock = asyncio.Lock()

    async def _ensure(self) -> ccxt.pro.kucoin:
        async with self._lock:
            if self._exchange is None:
                self._exchange = ccxt.pro.kucoin({"newUpdates": True})
            return self._exchange

    async def watch_ticker(
        self, native_symbol: str
    ) -> AsyncIterator[Ticker]:
        """Yield one Ticker per WS update until the caller stops iterating."""
        exchange = await self._ensure()
        ccxt_symbol = native_to_ccxt(native_symbol)  # "BTC-USDT" → "BTC/USDT"
        while True:
            try:
                raw = await exchange.watch_ticker(ccxt_symbol)
            except ccxt.BadSymbol as exc:
                raise SymbolNotFoundError(
                    user_input=native_symbol, venue="kucoin"
                ) from exc
            except ccxt.NetworkError:
                # ccxt.pro auto-reconnects; the yielded iterator rewinds
                continue
            yield CCXTAdapter.ticker_to_domain(raw, ...)

    async def close(self) -> None:
        if self._exchange is not None:
            await self._exchange.close()
            self._exchange = None
```

`newUpdates: True` — returns only the latest tick per call (we don't
need accumulated updates; each tick is processed independently).

### Rate-limiting / backoff

ccxt.pro handles reconnects + exponential backoff internally. We do not
add a layer.

## Watch loop

```python
async def _run_watch_loop(
    state: WatchState, ws: KucoinWsProvider
) -> None:
    deadline_ms = state.started_at_ms + state.max_duration_sec * 1000
    try:
        async for ticker in ws.watch_ticker(state.symbol.native_symbol):
            state.current_price = ticker.last
            state.last_tick_at_ms = ticker.observed_at_ms
            state.pnl_quote, state.pnl_pct = _calc_pnl(state)

            for event in EventDetector.detect(state, ticker):
                state.events.append(event)
                if event.type in TERMINAL_EVENTS:
                    state.status = _terminal_status(event.type)
                    return

            if ticker.observed_at_ms >= deadline_ms:
                state.events.append(WatchEvent(type=TIMEOUT, ...))
                state.status = WatchStatus.TIMEOUT
                return
    except asyncio.CancelledError:
        state.status = WatchStatus.CANCELLED
        raise
    except Exception as exc:
        state.status = WatchStatus.ERROR
        state.events.append(WatchEvent(type=ERROR, details={"msg": str(exc)}))
        raise
```

## Event detection (pure function)

`EventDetector.detect(state, ticker) -> list[WatchEvent]`

- Iterate event types in priority order: terminal events first
  (stop/take/timeout), then non-terminal.
- Non-terminal events filtered by `state._fired_non_terminal` set.
- Terminal events stop the loop.

Pure function (no I/O, no time) → trivial to unit-test with parametrised
table of `(state, ticker) → expected events`.

## Error handling

| Origin | Translation |
|---|---|
| `ccxt.BadSymbol` in provider | `SymbolNotFoundError` → `ToolError` |
| `ccxt.NetworkError` | auto-retried by ccxt.pro (silent) |
| Provider unrecoverable (3 reconnects fail) | `ProviderUnavailableError` → loop sets `status=error` |
| `watch_id` not found | new `WatchNotFoundError` domain exception → `ToolError` |
| Validation (bad prices, bad duration) | `ValidationError` → `ToolError` |
| User cancels mid-flight | `asyncio.CancelledError` caught, `status=cancelled` |

## Testing strategy

**Unit (`tests/unit`):**

- `test_event_detector.py` — parametrised: `(state, price) → [events]`.
  Cover all 6 event types × long/short × fire-once semantics.
- `test_watch_state.py` — validation, P&L calculation, ring-buffer
  overflow.
- `test_position_watcher.py` — `PositionWatcher.start/stop/check` with a
  `FakeWsProvider` yielding scripted ticker sequence. Verify registry
  mutations, task cancellation, state transitions.

**Contract (`tests/contract`):**

- `test_watch_tool_schemas.py` — JSON schemas for the three tools.

**Integration (`tests/integration`, `@pytest.mark.integration`):**

- `test_watch_kucoin_live.py` — real `ccxt.pro.kucoin` against KuCoin WS.
  Start watch → read ≥3 ticks → stop → assert status=cancelled, ≥3
  ticks recorded. Marked skip if `SKIP_LIVE_TESTS=1`.

## Performance budget

- Watch startup: ≤ 200 ms (return `watch_id` before first WS tick)
- `check_watch` latency: ≤ 10 ms (dict read + DTO build)
- `stop_watch` latency: ≤ 200 ms (cancel + await task unwind)
- Memory per watch: ~ 4 KB (state + 200-event ring buffer)
- One shared ccxt.pro instance supports ≥ 50 concurrent watches
  comfortably (KuCoin limit is 100 subscriptions / connection).

## Out of scope (deferred)

- `volume_spike` event (needs rolling average over N ticks)
- `level_broken` event (needs S/R analysis — already a separate
  `analyze_snapshot` tool; could be reused in v2)
- Persistence across server restarts (Redis-backed registry)
- Multi-venue (only kucoin WS in v1 — CoinGecko has no WS)
- Auto stop-to-breakeven (event fires; user acts manually)

## Open risks

1. **ccxt.pro stability against KuCoin long-running connections.**
   Mitigation: integration test runs for ≥ 30 s to smoke-test
   reconnect behaviour.
2. **Event loop blocking if any tool does sync I/O in the main loop.**
   Mitigation: existing project is fully async; verified in code
   review.
3. **Registry leak on long sessions.** No eviction — terminated watches
   accumulate. Mitigation: v1 adds a 100-watch cap with FIFO eviction
   of terminated entries.

## Implementation order (for plan)

1. `domain/watch.py` — `WatchSide`, `WatchStatus`, `EventType`,
   `WatchEvent`, `WatchState` + validation
2. `application/services/position_watcher.py` — `EventDetector`,
   `PositionWatcher` (start/stop/check), watch loop
3. `infrastructure/providers/kucoin_ws.py` — `KucoinWsProvider`
4. Lifespan wiring: `lifespan_state.py` keys, `bootstrap.py` init,
   cleanup in `server.py`
5. MCP tools: `mcp/tools/watch.py` + DTOs in `mcp/dtos.py` +
   `register_watch_tools` in `server.py`
6. Unit tests (per file above)
7. Integration test (gated on `SKIP_LIVE_TESTS`)
8. Update `CHANGELOG.md`, plugin `commands/` if we add a
   `/cryptozavr:watch` slash command (optional, v1 can skip)
