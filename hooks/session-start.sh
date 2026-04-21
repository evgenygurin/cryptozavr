#!/usr/bin/env bash
# SessionStart hook — prints a short banner so the user sees the plugin
# is loaded and lists the canonical entry points.
set -euo pipefail

cat <<'EOF'
# cryptozavr plugin loaded

Slash commands:
  /cryptozavr:ticker <venue> <symbol>           — fetch latest ticker
  /cryptozavr:ohlcv <venue> <symbol> <timeframe> — fetch OHLCV candles
  /cryptozavr:research <venue> <symbol>          — 4-tool research collage
  /cryptozavr:health                             — MCP server smoke test

Subagent: crypto-researcher (for multi-step market research)

Venues seeded: kucoin, coingecko
Need the 4 MCP tools? They auto-register from .mcp.json.
EOF
