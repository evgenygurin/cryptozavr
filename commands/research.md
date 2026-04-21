---
description: Multi-tool research collage — ticker + OHLCV (1h, 24 candles) + order book + recent trades for a symbol.
argument-hint: <venue> <symbol>
allowed-tools:
  - "mcp__cryptozavr-research__get_ticker"
  - "mcp__cryptozavr-research__get_ohlcv"
  - "mcp__cryptozavr-research__get_order_book"
  - "mcp__cryptozavr-research__get_trades"
---

Build a research snapshot for the user's symbol.

Run these 4 MCP tools in parallel (single message, multiple tool calls):
1. `get_ticker(venue, symbol)` — current price + 24h stats
2. `get_ohlcv(venue, symbol, timeframe="1h", limit=24)` — last 24 hourly candles
3. `get_order_book(venue, symbol, depth=20)` — top 20 levels each side
4. `get_trades(venue, symbol, limit=50)` — last 50 trades

Present the result in this structure:

### Price
- Last / bid / ask / spread_bps
- 24h range (from OHLCV high/low)
- 24h volume

### Trend (last 24h)
- Direction: up/down/flat based on first vs last OHLCV close
- Largest single-candle move (% of close)

### Liquidity
- Top bid × size vs top ask × size
- Spread in bps

### Recent flow
- Buy/sell ratio from trades (by count and by size)

### Provenance
- `reason_codes` from each tool, concatenated on one line per tool
- Warn if any `staleness != "fresh"` or `cache_hit=true` for price-sensitive fields

If `$ARGUMENTS` is empty, ask the user for venue and symbol.
