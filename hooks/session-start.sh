#!/usr/bin/env bash
# SessionStart hook — prints a short banner so the user sees the plugin
# is loaded and lists the canonical entry points.
set -euo pipefail

cat <<'EOF'
# cryptozavr plugin loaded

Slash commands:
  /cryptozavr:ticker <venue> <symbol>              — fetch latest ticker
  /cryptozavr:ohlcv <venue> <symbol> <timeframe>   — OHLCV candles
  /cryptozavr:research <venue> <symbol>            — 4-tool research collage
  /cryptozavr:resolve <user_input> [venue]         — fuzzy symbol lookup
  /cryptozavr:trending                             — CoinGecko trending + categories
  /cryptozavr:health                               — MCP server smoke test

Subagent:
  crypto-researcher — multi-step market research specialist

MCP prompts (cross-client):
  research_symbol(venue, symbol)   — 4-tool research template
  risk_check(venue, symbol)        — data-quality pre-decision check

MCP resources:
  cryptozavr://venues              — supported venues
  cryptozavr://symbols/{venue}     — symbols per venue
  cryptozavr://trending            — trending assets (CoinGecko)
  cryptozavr://categories          — market categories (CoinGecko)

Venues seeded: kucoin, coingecko
Tools: echo, get_ticker, get_ohlcv, get_order_book, get_trades, resolve_symbol.

Venue health: query resource cryptozavr://venue_health
  (state: healthy|degraded|down, last_checked_ms per venue — run /cryptozavr:health once MCP is up).
EOF
