---
description: Fetch OHLCV candles (open/high/low/close/volume) for a symbol + timeframe.
argument-hint: <venue> <symbol> <timeframe> [limit]
allowed-tools: ["mcp__cryptozavr-research__get_ohlcv"]
---

Fetch OHLCV candles for the user's requested symbol.

Parse `$ARGUMENTS` as: `<venue> <symbol> <timeframe> [limit]`.

Supported timeframes: `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1w`.

Call the `get_ohlcv` MCP tool with:
- `venue`, `symbol`, `timeframe` from args
- `limit`: default `100`, or 4th arg if provided (1..1000)
- `force_refresh`: `false`

Render the candles as a compact table (opened_at, open, high, low, close, volume). Highlight the last closed candle. Append the `reason_codes` audit trail.
