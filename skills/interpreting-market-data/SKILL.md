---
name: interpreting-market-data
description: Use when you've just received output from a cryptozavr MCP tool (ticker, OHLCV, orderbook, trades) and need to read it correctly. Covers field meanings, staleness flags, reason_codes, and common pitfalls.
---

# Interpreting cryptozavr market data

## Common fields

All tool outputs include:
- `venue`, `symbol` — where the data came from
- `reason_codes: list[str]` — ordered audit trail of the 5-handler chain:
  - `venue:healthy|degraded|rate_limited|down`
  - `symbol:found`
  - `cache:bypassed` (force_refresh=true)
  - `cache:hit` (Supabase returned cached) OR `cache:miss` + `provider:called`
  - `cache:write_failed` (upsert couldn't persist; response still valid)
- `staleness: "fresh"|"recent"|"stale"|"expired"`
- `confidence: "high"|"medium"|"low"`
- `cache_hit: bool`

## get_ticker

- `last` is the latest trade price. `bid`/`ask` may be None for CoinGecko (aggregator, no order book).
- `volume_24h` is in BASE units (BTC, not USDT).
- `observed_at_ms` is when the exchange stamped the data — may lag by seconds-minutes.

## get_ohlcv

- `candles: list[OHLCVCandleDTO]` ordered oldest → newest.
- Each candle's `closed: bool` — the last candle may be `closed=false` (still in-progress).
- `range_start_ms` / `range_end_ms` bracket the series; useful for windowing.

## get_order_book

- `bids` sorted highest-price-first; `asks` lowest-price-first.
- `spread` = `asks[0].price - bids[0].price`.
- `spread_bps` = spread / midpoint × 10000 — 10 bps is tight, 50 bps is wide.
- Empty `bids` or `asks` → `spread` is `None`.

## get_trades

- `trades` ordered newest → oldest.
- `side: "buy"|"sell"` from the taker's perspective (taker buy = demand).
- `trade_id` may be `null` for CoinGecko.

## Red flags to call out

1. `staleness == "stale"` or `"expired"` — suggest `force_refresh=true`.
2. `cache_hit=true` on volatile prices (tick-by-tick). Warn if the caller needs fresh data.
3. `cache:write_failed` in reasons — data is real, but the Supabase write didn't land. Non-fatal.
4. `venue:degraded` — upstream exchange is slow/errorful. Reduce expectations.
