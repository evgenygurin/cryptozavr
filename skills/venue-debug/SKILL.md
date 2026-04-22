---
name: venue-debug
description: Use when a cryptozavr tool returns degraded/stale data, times out, or reports an upstream failure (KuCoin/CoinGecko). Walks through the L2 infrastructure chain, inspects provider metrics, and pinpoints whether the issue is rate limiting, transport, provider downtime, or cache staleness.
---

# Venue Debug Workflow

Use this skill when any `get_ticker` / `get_ohlcv` / `get_order_book` / `get_trades`
call fails, returns stale data, or surfaces reason codes that do not match
expectations. The goal is to pinpoint **where in the L2 chain** the fault is,
not to blindly retry.

## Symptoms → starting points

| Symptom | Start with |
|---|---|
| "provider unavailable" / timeout | Step 1 (health) → Step 3 (HTTP pool) |
| `staleness != "fresh"` | Step 2 (cache) → Step 4 (sync worker) |
| `rate_limited` reason code | Step 3 (rate limiters) |
| intermittent silent failures | Step 5 (metrics) |

## The chain (reminder)

```text
LoggingDecorator
  └── InMemoryCachingDecorator (ticker_ttl=5s, ohlcv_ttl=60s, order_book_ttl=3s)
      └── RateLimitDecorator (TokenBucket per venue)
          └── RetryDecorator (3 attempts, exponential backoff)
              └── MetricsDecorator (provider_calls_total, duration_ms)
                  └── base provider (CCXT or CoinGecko HTTP)
```

## Step 1 — Check venue health

Read `cryptozavr://venue_health` (or run `/cryptozavr:health`). Verify the
`state` and `last_checked_ms` fields for the venue in question.

- `down` → skip to Step 3.
- `degraded` → HealthMonitor saw at least one probe failure; go to Step 5.
- `healthy` but tool still fails → go to Step 2.

## Step 2 — Check the cache

Look at the tool response `reason_codes`:

- `cache:hit` with unexpected stale data → a realtime invalidation did not
  fire. Check `CacheInvalidator.on_ticker_change` logs.
- `cache:miss` → cache was cold; next step is whether the upstream call
  succeeded. Go to Step 3.

## Step 3 — Rate limits + HTTP pool

- `rate_limited` outcome in `venue_health_check_total` counter → the venue
  exceeded its TokenBucket. Confirm bucket config in
  `src/cryptozavr/mcp/bootstrap.py` (`RateLimiterRegistry.register`).
- Transport failures (`error` or `timeout` outcome without rate-limit cause)
  → inspect HTTP client pool in `src/cryptozavr/infrastructure/providers/http.py`.

## Step 4 — TickerSyncWorker / RealtimeSubscriber

If data staleness persists through cache TTL:

- Verify `RealtimeSubscriber.subscriptions()` returns the expected
  `(venue, symbol)` pairs.
- Confirm `TickerSyncWorker.is_running is True` in the running lifespan.
- Tail logs for `ticker sync failed for ...` warnings.

## Step 5 — Metrics snapshot

Aggregate counter outcomes from the shared `MetricsRegistry`:

```text
provider_calls_total{venue=kucoin, endpoint=fetch_ticker, outcome=rate_limited}
provider_calls_total{venue=kucoin, endpoint=fetch_ticker, outcome=error}
venue_health_check_total{venue=kucoin, outcome=timeout}
```

Compare against `provider_call_duration_ms` histogram — a sudden bucket shift
above 1000ms is a transport-level regression.

## Recap template

When reporting to the user, use this 5-line format:

```text
Venue: <kucoin|coingecko>
Symptom: <exact reason codes or error>
Chain layer: <cache|rate_limit|retry|provider>
Root cause: <one sentence>
Fix: <config change | restart | downstream incident>
```
