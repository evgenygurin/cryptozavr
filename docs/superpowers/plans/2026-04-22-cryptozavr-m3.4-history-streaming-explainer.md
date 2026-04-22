# cryptozavr — Milestone 3.4: History streaming + SessionExplainer (compact plan)

**Goal:** Close the MVP surface. Add (1) `OHLCVPaginator` + `fetch_ohlcv_history` MCP tool that streams large historical windows with `ctx.report_progress`, and (2) lightweight `SessionExplainer` that wraps every tool response in the `{data, quality, reasoning}` envelope the spec calls for.

**Idiomatic per M3.0/M3.3:** `Depends` DI, direct Pydantic return, `ctx.info`/`ctx.report_progress`, `timeout`, `meta`, `ToolError` via `domain_to_tool_error`.

**Starting tag:** `v0.1.4`. Target: `v0.2.0` (MVP closure).

## Scope decisions

- **No `task=True`** (FastMCP background tasks) for now — `ctx.report_progress` inside a long-running sync tool is enough for UX and avoids pulling in the `docket` task infrastructure. Can lift in a later phase.
- **SessionExplainer is a helper, not a class hierarchy.** Single function `build_envelope(data, quality, reason_codes, query_id)` → `dict`. Callers decide when to wrap. Existing tools keep returning their DTOs directly (no breaking change); only the new `fetch_ohlcv_history` tool returns the envelope as its primary wire format.

## Tasks

1. **OHLCVPaginator (Iterator) + unit tests** — `async for` over `(timeframe, since, until)` yielding candle chunks ≤ chunk_size (default 500). Uses `OhlcvService.fetch_ohlcv(limit=chunk_size, since=cursor, force_refresh=False)` under the hood. Cursor advances by `timeframe.milliseconds * chunk_size`. Tests cover: single-chunk window, multi-chunk span, partial last chunk, empty response short-circuit.

2. **OHLCVSeries concat helper + history DTO** — `OHLCVHistoryDTO` (venue/symbol/timeframe/range_start_ms/range_end_ms/candles/reason_codes/chunks_fetched). Reuses `OHLCVCandleDTO.from_domain`. Decimal-safe via `model_dump(mode="json")` in structured content auto-generation.

3. **`fetch_ohlcv_history` MCP tool** — `venue`, `symbol`, `timeframe`, `since_ms`, `until_ms`, optional `chunk_size=500`, `force_refresh=False`. Iterates `OHLCVPaginator`, emits `ctx.report_progress(chunks_done, total_chunks_est, msg)`. `timeout=180s`, `meta={version, mode: "history"}`. Total-chunks estimate: `ceil((until - since) / (timeframe.ms * chunk_size))`.

4. **SessionExplainer helper + 1 demo wiring** — `src/cryptozavr/mcp/explainer.py::build_envelope(data, quality, reason_codes, query_id=None)` → `dict`. `query_id` defaults to `uuid4().hex[:12]` when unset. Plug into `fetch_ohlcv_history` to prove the pattern; leave existing tools untouched.

5. **Wire + slash command + banner** — `OhlcvService.fetch_ohlcv_history_stream()` returns the paginator. Bootstrap wires nothing new (paginator constructed per-tool-call). Add `/cryptozavr:history` slash command, update `/cryptozavr:health` banner. Add server_startup test asserting the new tool is registered.

6. **CHANGELOG + tag v0.2.0 + push** — mark MVP closure. Update plugin surface to 11 tools / 4 resources / 2 prompts / 8 slash commands.

Target: ~20 new unit tests, plugin surface → **11 tools** (+1 history).
