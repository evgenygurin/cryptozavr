---
description: Stream OHLCV history across a time window — pages through chunks and returns a SessionExplainer envelope.
argument-hint: <venue> <symbol> <timeframe> <since_ms> <until_ms> [chunk_size]
allowed-tools:
  - "mcp__plugin_cryptozavr_cryptozavr-research__fetch_ohlcv_history"
---

Fetch a streamed OHLCV window.

Parse `$ARGUMENTS` as: `<venue> <symbol> <timeframe> <since_ms> <until_ms> [chunk_size]`.
Defaults: `chunk_size=500`.

Call `fetch_ohlcv_history(venue, symbol, timeframe, since_ms, until_ms, chunk_size)`.
The tool emits progress updates between chunks and returns the
`{data, quality, reasoning}` envelope.

Present the result in this structure:

### Window
- symbol, venue, timeframe
- range_start_ms → range_end_ms (format as human-readable UTC dates)
- total candles returned, chunks_fetched (how many upstream fetches backed the response)

### Price action (sampled)
- First candle close, last candle close
- Best/worst candle (% move)

### Quality
- From `envelope.quality`: staleness, confidence, cache_hit, fetched_at_ms

### Provenance
- `reasoning.query_id` — carry this in follow-up tool calls for correlation
- `reasoning.chain_decisions` — full audit trail across every chunk

If `$ARGUMENTS` is empty or missing `since_ms`/`until_ms`, ask the user
for the full window.
