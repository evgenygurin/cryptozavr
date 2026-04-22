# Long-poll watcher pattern on FastMCP v3

**Date:** 2026-04-22
**Context:** cryptozavr v0.3.4 — `watch_position` + `wait_for_event` shipped on the KuCoin WebSocket ticker stream
**Audience:** engineers building MCP servers around live data feeds

## Problem

We needed clients (LLMs, dashboards) to **react within a second** to terminal events on a paper-trading position watcher:

- `stop_hit` / `take_hit` on a live price crossing a threshold
- `timeout` when a max-duration elapses
- Fire-once milestones (`price_approaches_stop/take`, `breakeven_reached`)

Events are produced by a background coroutine consuming a KuCoin WebSocket `watch_trades` subscription — unpredictable arrival, sometimes hundreds of milliseconds apart, sometimes minutes of silence.

FastMCP v3 ships two mechanisms that *look* like fits but don't solve this:

### Not: `ctx.set_state / get_state`

Session-scoped state ([docs](https://gofastmcp.com/docs/servers/context)) stores values keyed by session id. Great for per-session caches. Wrong here because:

- State is passive — no primitive to wake a waiting caller when a value changes.
- TTL is 1 day; we want tight lifecycle tied to a watch.
- Doesn't carry queue semantics (`since_event_index` cursors).

### Not: `@mcp.tool(task=True)` (Docket)

The protocol-native background task system ([docs](https://gofastmcp.com/docs/servers/tasks), [SEP-1686](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks)) is for **fire-and-forget jobs** that finish with a result. Client starts task, polls every `poll_interval` seconds (default 5s), eventually gets the return value.

Wrong here because:

- Polling floor is seconds, not milliseconds.
- "Task" is one-shot: start → complete, not start → stream-of-events → terminate.
- Requires Docket + Redis for anything beyond single-process `memory://`.
- We want the client to *drive the lifecycle* with explicit start/wait/stop tool calls.

FastMCP's own elicitation code actually made the same transition — from polling to Redis BLPOP (#2906 in `v3-features.mdx`) — because "check every N seconds" is wrong when events are latency-critical. We went one step further: purely in-process, no Redis, using `asyncio.Condition` as the blocking primitive.

## Pattern

A **reactive long-poll tool** that blocks until one of three things happens: a new event is appended, the watch reaches a terminal status, or a client-provided timeout expires.

### Shape

```python
# domain/watch_state.py
from dataclasses import dataclass, field
from typing import Literal
import asyncio

Status = Literal["running", "stop_hit", "take_hit", "timeout", "cancelled", "error"]

@dataclass
class Event:
    type: str
    ts_ms: int
    price: Decimal

@dataclass
class WatchState:
    watch_id: str
    status: Status = "running"
    events: list[Event] = field(default_factory=list)
    # Not a default_factory for asyncio.Condition — eagerly create in __post_init__
    _change_cond: asyncio.Condition = field(init=False)

    def __post_init__(self) -> None:
        self._change_cond = asyncio.Condition()

    async def append_event(self, event: Event) -> None:
        async with self._change_cond:
            self.events.append(event)
            self._change_cond.notify_all()

    async def set_status(self, status: Status) -> None:
        async with self._change_cond:
            self.status = status
            self._change_cond.notify_all()
```

```python
# application/services/position_watcher.py (sketch)
class PositionWatcher:
    def __init__(self, ws_provider: WsProvider) -> None:
        self._ws = ws_provider
        self._states: dict[str, WatchState] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    async def start(self, spec: WatchSpec) -> str:
        state = WatchState(watch_id=generate_id(), ...)
        self._states[state.watch_id] = state
        self._tasks[state.watch_id] = asyncio.create_task(self._run(state, spec))
        return state.watch_id

    async def _run(self, state: WatchState, spec: WatchSpec) -> None:
        try:
            async for tick in self._ws.watch_trades(spec.symbol):
                if spec.approaches_stop(tick.price) and not state.has("price_approaches_stop"):
                    await state.append_event(Event("price_approaches_stop", tick.ts_ms, tick.price))
                if spec.stop_hit(tick.price):
                    await state.append_event(Event("stop_hit", tick.ts_ms, tick.price))
                    await state.set_status("stop_hit")
                    return
                # ... rest of the event grammar
        except asyncio.CancelledError:
            await state.set_status("cancelled")
            raise
        except Exception as e:
            await state.set_status("error")
            raise

    async def stop(self, watch_id: str) -> WatchState:
        task = self._tasks.pop(watch_id, None)
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        state = self._states[watch_id]
        if state.status == "running":
            await state.set_status("cancelled")
        return state
```

```python
# mcp/tools/watcher.py
@mcp.tool
async def wait_for_event(
    watch_id: str,
    since_event_index: int = 0,
    timeout_sec: Annotated[int, Field(ge=1, le=600)] = 300,
    ctx: Context = CurrentContext(),
) -> WatchSnapshotDTO:
    watcher: PositionWatcher = ctx.lifespan_context["watcher"]
    state = watcher.get(watch_id)  # raises ToolError if unknown

    async def _has_progress() -> bool:
        return len(state.events) > since_event_index or state.status != "running"

    async with state._change_cond:
        try:
            await asyncio.wait_for(
                state._change_cond.wait_for(_has_progress),
                timeout=timeout_sec,
            )
        except asyncio.TimeoutError:
            pass  # Not an error — return the current snapshot

    return state.to_snapshot(since_event_index=since_event_index)
```

### Lifespan wiring

```python
@lifespan
async def cryptozavr_lifespan(server: FastMCP) -> AsyncGenerator[dict]:
    ws_provider = KucoinWsProvider()
    await ws_provider.start()
    watcher = PositionWatcher(ws_provider)
    try:
        yield {"ws_provider": ws_provider, "watcher": watcher}
    finally:
        await watcher.shutdown()    # cancels every running asyncio.Task
        await ws_provider.close()
```

`watcher.shutdown()` iterates `_tasks`, calls `task.cancel()`, awaits each, and sets status `cancelled` on any survivor. This is the crucial teardown that `docs/servers/lifespan.mdx` doesn't cover explicitly: long-running `asyncio.create_task` handles **must** be captured and cancelled in `finally`, or they become zombies on server shutdown.

## Measured latency

From session `200e6165-3127-427e-a07d-82ce345efbc9` (2026-04-22, cryptozavr v0.3.4, KuCoin live `watch_trades`, BTC-USDT):

| Event | Wall-clock delta from preceding WS tick |
|-------|----------------------------------------|
| `price_approaches_stop` → `stop_hit` terminal | **488 ms** |
| `timeout` fire vs `expected_end_at_ms` | < 1 s (aligned to next WS tick) |
| First-event early-return from 300s long-poll | 15 s (price moved quickly after open) |

Compared to the legacy pattern (one `check_watch` per `sleep 60s`), terminal-event reaction dropped from ~60 s worst case to ~500 ms — a 120× improvement driven entirely by the Condition primitive replacing the sleep loop.

## Gotchas

1. **Miss one `notify_change` call and you hang forever.**
   Every mutation point must notify: `append_event`, `set_status`, cancellation handler, error path in `_run`, `stop()`. A single missed path means `wait_for_event` blocks until `timeout_sec`. We enforce this by routing all mutations through `WatchState` methods rather than setting attributes directly.

2. **The predicate must cover both "new event" AND "terminal status".**
   If the predicate only checks `len(events) > since_event_index`, a clean `timeout` → `cancelled` transition with no final event strand-locks the caller.

3. **`asyncio.wait_for` wraps the `wait_for` on the Condition.**
   Python 3.11+ `asyncio.Condition.wait_for` itself has no timeout argument. Don't try to emulate with `wait()` + manual check — the outer `asyncio.wait_for` is cleaner and cancels the inner wait correctly.

4. **`WatchState` is in-memory, not persisted.**
   A `pkill -f mcp.server` (see `feedback_plugin_mcp_ops.md`) drops every running watch silently. Accept this (our stance) or persist to Supabase with a `watch_id` row per state. Do not try to re-hydrate mid-session from disk — you'll fight your own asyncio cancellation.

5. **Events can appear with `ts_ms < started_at_ms`.**
   Early versions of `PositionWatcher` had shared approach-event state across watches on the same symbol. Fixed by scoping event memory to the `WatchState` instance. Verify test `test_multi_watch_events_isolated` covers this if you evolve the watcher.

6. **`since_event_index=<next_event_index from previous response>` is not optional.**
   Without it, every `wait_for_event` re-returns the same terminal event, the client loops forever thinking it's making progress. This is a client-side discipline — make sure agent prompts spell it out.

## When NOT to use this pattern

- **Job that eventually returns a result.** Use `@mcp.tool(task=True)` — Docket is built for this, survives restarts, scales horizontally.
- **Single "did price cross N?" check.** Use `get_ticker` + compare. Don't spin up state machinery for a one-shot question.
- **Multi-client aggregation (fan-out).** Condition only wakes current-process waiters; across servers you need a real message bus (Redis pub/sub, NATS).

## References

- FastMCP docs read in prep: `docs/servers/lifespan.mdx`, `docs/servers/tasks.mdx`, `docs/servers/dependency-injection.mdx`, `docs/development/v3-notes/v3-features.mdx` (sections: Background Task Notification Queue, Session-Scoped State, Composable Lifespans)
- Relevant FastMCP PR: [#2906 "notification queue → BLPOP"](https://github.com/PrefectHQ/fastmcp/pull/2906) — same family of problem, different scope (cross-process, Redis-backed)
- MCP SEP-1686 (Background Tasks): https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks
- Our implementation: `src/cryptozavr/application/services/position_watcher.py`, `src/cryptozavr/mcp/tools/watcher.py`, tests in `tests/unit/application/services/test_position_watcher.py` + `tests/integration/test_kucoin_ws_live.py`

## Open questions / follow-ups

1. **File upstream FastMCP issue for parallel-batch MCP crash?** Two crashes in this session on ~8-way parallel tool batches across stdio. Needs minimal repro (bare FastMCP server, 8 trivial tools, Client.call_tool with asyncio.gather). Until then, document the workaround in `feedback_plugin_mcp_ops.md`.
2. **Promote `wait_for_event` to a FastMCP example?** The pattern is generic. Could land as `examples/long_poll_watcher/` showing a tiny temperature-sensor or stock-ticker mock. Contribution policy requires an issue first (contributing.mdx).
3. **Trailing-stop support via middleware?** Current all-or-nothing exits produce skewed PnL distribution (5W/5L session, avg win < avg loss). A `modify_watch(watch_id, new_stop=X)` tool is a one-line addition with `state.set_status` re-notifying; worth it once partial-take lands.
