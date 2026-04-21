# Changelog

All notable changes to cryptozavr will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.0.8] - 2026-04-21

### Added — M2.5 `get_ohlcv` tool + integration tests
- `OHLCVCandleDTO` / `OHLCVSeriesDTO` (Pydantic): wire formats for OHLCV data. Candle has opened_at_ms + OHLC + volume + closed; series has venue/symbol/timeframe/range/candles + reason_codes.
- `OhlcvService` (L4 Application): mirror of `TickerService` — validates venue/symbol, builds the `build_ohlcv_chain` per request with `FetchOperation.OHLCV`, returns `OhlcvFetchResult` (series + reason codes).
- `register_ohlcv_tool(mcp)`: `get_ohlcv(venue, symbol, timeframe, limit, force_refresh)` validates timeframe string → `Timeframe` enum (unknown → ValidationError → ToolError), reads `OhlcvService` from lifespan_context, catches `DomainError`, returns `OHLCVSeriesDTO`. `limit` bounded 1..1000.
- `AppState` now carries both `ticker_service` and `ohlcv_service`. `build_production_service` returns a triple `(ticker_service, ohlcv_service, cleanup)`.
- Integration tests: `tests/integration/mcp/test_tools_integration.py` runs `get_ticker` and `get_ohlcv` through the real FastMCP lifespan against live Supabase + KuCoin. Marked `@pytest.mark.integration`; auto-skip when `SUPABASE_DB_URL` / related vars are absent or Supabase is unreachable.
- 14 new unit tests (OHLCV DTOs 4 + OhlcvService 5 + get_ohlcv tool 3 + 2 integration skip-safe). Total 260 unit + 5 contract + 2 integration (skip-safe).

### Next
- M2.6: `get_order_book`, `get_trades` (non-cached); refine Realtime stub (phase 1.5 prep).

## [0.0.7] - 2026-04-21

### Added — M2.4 First MCP tool `get_ticker` (full stack)
- `TickerDTO` (Pydantic): wire format with `venue`, `symbol`, `last`, `bid`, `ask`, `volume_24h`, `observed_at_ms`, `staleness`, `confidence`, `cache_hit`, `reason_codes`. `from_domain` factory.
- `domain_to_tool_error`: maps `SymbolNotFoundError` / `VenueNotSupportedError` / `RateLimitExceededError` / `ProviderUnavailableError` / `ValidationError` / generic `DomainError` into user-facing `fastmcp.exceptions.ToolError`.
- `TickerService` (L4 Application orchestrator): validates venue/symbol, builds the 5-handler chain per request, returns `TickerFetchResult` (ticker + reason codes). Unknown venue or symbol raises the matching domain exception.
- `register_ticker_tool(mcp)`: `get_ticker(venue, symbol, force_refresh)` reads `TickerService` from `ctx.lifespan_context`, catches `DomainError`, returns `TickerDTO`.
- `build_production_service(settings)`: wires `HttpClientRegistry`, `RateLimiterRegistry` (kucoin 30 rps, coingecko 0.5 rps), `SymbolRegistry` seeded with BTC-USDT + ETH-USDT on KuCoin, per-venue `VenueState`, `SupabaseGateway` over asyncpg pool, `ProviderFactory`-wrapped KuCoin + CoinGecko providers. Returns `(service, cleanup)`.
- `build_server(settings)` now owns a FastMCP v3 `lifespan` that opens and closes all infra around `TickerService`. `FastMCP[AppState]` generic for typed lifespan context.
- Manual smoke-test note: `docs/superpowers/m2.4-smoke-test.md`.
- 17 new unit tests (TickerDTO 3 + errors 6 + TickerService 5 + get_ticker tool 3). Total ≥248 unit + 5 contract.

### Next
- M2.5: second tool (`get_ohlcv`) + Realtime subscribe stub + integration tests against live Supabase.

## [0.0.6] - 2026-04-21

### Added — M2.3c Chain of Responsibility + ProviderFactory
- `FetchOperation` enum (ticker/ohlcv/order_book/trades).
- `FetchRequest` (immutable) + `FetchContext` (mutable accumulator of reason_codes + metadata).
- `FetchHandler` abstract base with `set_next`/`_forward`.
- 5 concrete handlers: `VenueHealthHandler` (VenueState gate), `SymbolExistsHandler` (SymbolRegistry validation), `StalenessBypassHandler` (force_refresh → bypass_cache metadata), `SupabaseCacheHandler` (cache-aside via gateway), `ProviderFetchHandler` (terminal + write-through).
- `build_ticker_chain` / `build_ohlcv_chain` assembly helpers.
- `ProviderFactory` (Factory Method): `create_kucoin(state, exchange?)` / `create_coingecko(state)` return fully-wired providers (LoggingDecorator → CachingDecorator → RateLimitDecorator → RetryDecorator → base).
- 22 new unit tests (226 total); provider layer coverage ≥ 90%.

### Completes M2.3 Providers layer
All 14 GoF patterns from MVP design section 4 implemented: Template Method (BaseProvider), Adapter (CCXT/CoinGecko), Bridge (Domain Protocol ↔ concrete providers), Decorator (4 layered), Chain of Responsibility (5 handlers), State (VenueState + 4 handlers), Factory Method (ProviderFactory), Singleton via DI (registries), Flyweight (SymbolRegistry from M2.1), Observer (Supabase Realtime, deferred to phase 1.5).

### Next
- M2.4: First MCP tool `get_ticker` through full stack (Chain → Factory → Decorators → Provider → SupabaseGateway cache-aside).

## [0.0.5] - 2026-04-21

### Added — M2.3b Decorators + State + CoinGecko
- `CoinGeckoAdapter`: pure functions `simple_price_to_ticker`, `trending_to_assets`, `categories_to_list`.
- `CoinGeckoProvider`: BaseProvider subclass over httpx + HttpClientRegistry. Endpoints: `/simple/price`, `/search/trending`, `/coins/categories`. 429→RateLimitExceededError, connect/timeout→ProviderUnavailableError.
- CoinGecko fixtures (3 files) + contract tests (2 tests) via respx.
- `VenueState` upgraded to full State pattern with 4 handler classes (`HealthyStateHandler`, `DegradedStateHandler`, `RateLimitedStateHandler`, `DownStateHandler`). Automatic transitions: Healthy→Degraded (3 errors), Degraded→Healthy (5 successes), any→RateLimited (RateLimitExceededError, 30s cooldown), RateLimited→Healthy (expiry), any→Down (explicit `mark_down()`).
- 4 composable decorators: `RetryDecorator` (exponential backoff, excludes RateLimitExceededError), `RateLimitDecorator` (TokenBucket acquire), `InMemoryCachingDecorator` (TTL cache per method family), `LoggingDecorator` (stdlib logging with durations).
- Decorator chain integration test verifies `LoggingDecorator(CachingDecorator(RateLimitDecorator(RetryDecorator(base))))` composes correctly.

### Deferred to M2.3c
- Chain of Responsibility (5 handlers: VenueHealth, SymbolExists, StalenessBypass, SupabaseCache, ProviderFetch).
- `ProviderFactory` (Factory Method).

## [0.0.4] - 2026-04-21

### Added — M2.3a Core providers
- `HttpClientRegistry`: per-venue httpx.AsyncClient pool (Singleton via DI).
- `TokenBucket` + `RateLimiterRegistry`: classic token-bucket rate limiter with asyncio.Lock-safe acquire.
- `VenueState`: minimal State context holding current VenueStateKind; `require_operational()` raises on RATE_LIMITED/DOWN. Full transition rules in M2.3b.
- `BaseProvider`: Template Method skeleton (require_operational → ensure_markets → fetch_raw → normalize → translate_exception) for ticker/ohlcv/orderbook/trades pipelines.
- `CCXTAdapter`: pure static functions converting CCXT unified format to Domain (ticker/ohlcv/orderbook).
- `CCXTProvider`: concrete BaseProvider wrapping ccxt.async_support (`for_kucoin` classmethod convenience). Exception translation: CCXT.RateLimitExceeded → RateLimitExceededError; CCXT.NetworkError → ProviderUnavailableError.
- Contract tests: `tests/contract/` with saved KuCoin JSON fixtures (ticker/ohlcv/orderbook) and end-to-end provider test via FakeKucoin replay.
- New deps: ccxt, httpx (m2 group); respx, freezegun (dev group).

### Deferred to M2.3b
- CoinGeckoAdapter + CoinGeckoProvider.
- 4 Decorators: Retry, RateLimit, InMemoryCaching, Logging.
- Full VenueState transition rules (HealthyState/DegradedState/RateLimitedState/DownState behaviours).

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
