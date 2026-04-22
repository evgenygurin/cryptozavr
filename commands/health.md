---
description: Smoke-test the plugin — call the echo tool and confirm the MCP server is reachable.
argument-hint: ""
allowed-tools: ["mcp__plugin_cryptozavr_cryptozavr-research__echo"]
---

Call the `echo` MCP tool with message `"health-check"`. If it returns the echoed message + server version, report:

- ✅ MCP server reachable
- Version: <from response>
- Available tools: `echo`, `get_ticker`, `get_ohlcv`, `get_order_book`, `get_trades`, `resolve_symbol`, `compute_vwap`, `identify_support_resistance`, `volatility_regime`, `analyze_snapshot`, `fetch_ohlcv_history`

If the call errors or times out, report the error and suggest:
1. Verify `.env` has `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_URL`
2. Check `uv sync --all-extras` ran at plugin install
3. Try `/plugin marketplace update` to refresh
