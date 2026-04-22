---
description: Run composite analytics snapshot (VWAP + support/resistance + volatility) for a symbol.
argument-hint: <venue> <symbol> [timeframe] [limit]
allowed-tools:
  - "mcp__plugin_cryptozavr_cryptozavr-research__analyze_snapshot"
---

Run the composite analytics snapshot.

Parse `$ARGUMENTS` as: `<venue> <symbol> [timeframe] [limit]`.
Defaults: `timeframe=15m`, `limit=200`.

Call `analyze_snapshot(venue, symbol, timeframe, limit)` once — it runs
three strategies over a single OHLCV fetch and emits progress updates.

Present the result in this structure:

### Fair value
- `vwap` result — VWAP price, total volume used, bars counted, confidence

### Levels
- `support_resistance` result — list supports (low → high) and resistances
  (low → high), with pivots_found

### Volatility
- `volatility_regime` result — regime classification (calm/normal/high/
  extreme), ATR value, ATR as % of last close, bars_used

### Provenance
- `reason_codes` from the report
- Warn if any non-`staleness:fresh` codes appear or `cache:write_failed`

If `$ARGUMENTS` is empty, ask the user for venue and symbol.
