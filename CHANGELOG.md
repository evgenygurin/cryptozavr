# Changelog

All notable changes to cryptozavr will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.0.3] - 2026-04-21

### Added — M2.2 Supabase schema + Gateway
- SQL migrations (6 files): extensions (vector/pg_cron/pg_net/pg_trgm + cryptozavr schema), reference (venues/assets/symbols/symbol_aliases + 4 enums), market_data (tickers_live/ohlcv_candles/orderbook_snapshots/trades with indexes + composite PK on ohlcv), audit (query_log with halfvec(1536) reserved column + provider_events + 4 indexes), RLS policies (service_role bypass on all 10 tables), pg_cron jobs (prune-stale-tickers, prune-query-log).
- Seed: baseline kucoin + coingecko venues with capabilities.
- `SupabaseGateway` Facade: resolve_symbol_id, upsert_ticker/load_ticker, upsert_ohlcv/load_ohlcv, insert_query_log, realtime/storage/rpc stubs, close.
- `PgPoolConfig` + `create_pool` for asyncpg connection pool.
- Row mappers (pure functions, 100% unit coverage): row_to_symbol, row_to_ticker, row_to_ohlcv_candle, row_to_ohlcv_series.
- Stubs for phase-later integrations: `RealtimeSubscriber` (phase 1.5), `StorageClient` (phase 2+), `RpcClient` (phase 2+).
- Integration tests (auto-skip when Supabase not running): migrations apply verification, OHLCV upsert→load roundtrip + idempotency, ticker upsert→load + overwrite, query_log insert with/without symbol.
- New dev deps: asyncpg, supabase, realtime (M2 optional group + dev group).
- 10 new unit tests (mappers + pg_pool); 11 integration tests (skip-safe).

### Deferred
- Task 9 (apply migrations to live Supabase) — Docker daemon was stopped at finalize time. Run `supabase start && supabase db push` + `supabase db reset` locally, or `supabase link --project-ref <cloud-ref> && supabase db push` for cloud, then rerun `uv run pytest tests/integration -m integration`.

## [0.0.2] - 2026-04-21

### Added — M2.1 Domain layer
- Value objects: `Timeframe`, `Instant`, `TimeRange`, `Money`, `Percentage`, `PriceSize`.
- Quality types: `Staleness` (ordered FRESH<RECENT<STALE<EXPIRED), `Confidence`, `Provenance`, `DataQuality` envelope.
- Entities: `Asset` + `AssetCategory`, `Venue` + 5 enums, `Symbol` + `SymbolRegistry` (Flyweight).
- Market data: `Ticker`, `OHLCVCandle`, `OHLCVSeries` (with slice/window), `OrderBookSnapshot` (with spread/spread_bps), `TradeTick`, `TradeSide`, `MarketSnapshot` composite.
- Protocol interfaces: `MarketDataProvider`, `Repository[T]`, `Clock`.
- Exception hierarchy: `DomainError` root + 4 families (ValidationError, NotFoundError, ProviderError, QualityError) with domain-specific subtypes.
- Dev deps: `hypothesis`, `polyfactory` for property-based and factory-driven tests.
- 114 unit tests, domain coverage ≥ 94%.

### Fixed
- `Instant.to_ms()` uses `round()` instead of `int()` to preserve roundtrip precision (hypothesis property-based regression).

## [0.0.1] - 2026-04-21

### Added — M1 Bootstrap
- Repository initialization with git, uv, ruff, mypy, pytest, pre-commit.
- Claude Code plugin manifest (`plugin.json`, `.mcp.json`).
- FastMCP v3+ server skeleton with `echo` smoke tool.
- Supabase CLI init with `cryptozavr` schema reserved.
- CI pipelines: lint + typecheck + unit tests, plugin artefact validation.
- Documentation: README, CHANGELOG, design spec, M1 implementation plan.
