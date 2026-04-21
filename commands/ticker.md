---
description: Fetch latest ticker (last/bid/ask/volume/24h-change) for a symbol on a venue.
argument-hint: <venue> <symbol>
allowed-tools: ["mcp__plugin_cryptozavr_cryptozavr-research__get_ticker"]
---

Fetch the ticker for the user's requested symbol.

Call the `get_ticker` MCP tool with:
- `venue`: first argument (e.g. `kucoin`, `coingecko`)
- `symbol`: second argument (e.g. `BTC-USDT`)
- `force_refresh`: `false`

After receiving the result, present:
1. Last price (bold), bid/ask spread, 24h volume
2. `reason_codes` audit trail (one line, comma-separated)
3. `staleness` + `cache_hit` — so the user knows how fresh the data is

If `$ARGUMENTS` is empty or missing a value, ask the user for the venue and symbol before calling the tool.
