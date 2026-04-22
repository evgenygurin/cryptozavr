---
description: Smoke-test the plugin — echo + read cryptozavr://venue_health.
argument-hint: ""
allowed-tools: ["mcp__plugin_cryptozavr_cryptozavr-research__echo"]
---

Run two checks in parallel:

1. Call the `echo` MCP tool with message `"health-check"`.
2. Read the MCP resource `cryptozavr://venue_health`.

Then report:

- ✅ MCP server reachable — include server version from the echo response.
- Venue health — one line per venue from the resource payload:
  `<venue>: <state> (last_checked_ms=<value or null>)`.
- Available tools: `echo`, `get_ticker`, `get_ohlcv`, `get_order_book`, `get_trades`, `resolve_symbol`, `compute_vwap`, `identify_support_resistance`, `volatility_regime`, `analyze_snapshot`, `fetch_ohlcv_history`.

If either call errors or times out, report the error and suggest:
1. Verify `.env` has `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_URL`.
2. Check `uv sync --all-extras` ran at plugin install.
3. Try `/plugin marketplace update` to refresh.
