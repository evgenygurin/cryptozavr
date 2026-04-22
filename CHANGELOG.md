# Changelog

All notable changes to cryptozavr will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — Phase 2B.1 — Streaming indicator engine

- `cryptozavr.application.backtest.indicators` package with an `Indicator`
  Protocol (`update(candle) -> Decimal | None`, `is_warm`, `period`) and
  6 concrete implementations: `SimpleMovingAverage`,
  `ExponentialMovingAverage`, `RelativeStrengthIndex`, `MACD` (line only),
  `AverageTrueRange`, `VolumeIndicator`.
- `create_indicator(IndicatorRef) -> Indicator` factory maps 2A's DSL
  references to concrete streaming instances — fresh independent state
  per call.
- `extract_price(candle, PriceSource)` helper — HLC3 uses exact Decimal
  division (no float drift).
- Algorithmic choices: SMA uses O(1) rolling-sum subtraction; EMA seeds
  with SMA of first `period` bars then applies classic alpha smoothing;
  RSI and ATR use Wilder smoothing; RSI returns 100 when `avg_loss == 0`
  (max-bullish convention). MACD signal/histogram deferred — exposing
  them would need a 2A+1 DSL extension.
- 48 new unit tests: warm-up semantics, hand-computed references,
  property-based sliding-window match for SMA, ground-truth RSI.
- No `BacktestReport` / MCP / persistence surface at this layer — pure
  streaming math consumed by 2B.2 (condition evaluator) + 2B.3 (trade
  simulator) in subsequent sub-phases.

### Added — Phase 2A — Declarative strategy DSL + Builder

- `cryptozavr.application.strategy` package with 4 frozen Pydantic DTOs
  (`IndicatorRef`, `Condition`, `StrategyEntry`, `StrategyExit`) and the
  aggregate `StrategySpec`. Enums (`StrategySide`, `IndicatorKind`,
  `ComparatorOp`, `PriceSource`) ship lowercase-snake values as the
  wire contract for future 2D MCP tools + 2E Supabase persistence.
- `StrategySpecBuilder` — fluent, immutable step-by-step constructor
  backed by a frozen dataclass and `dataclasses.replace`. Pattern #16
  (Builder) shipped.
- Cross-field invariants: non-empty entry conditions, at-least-one exit
  path (conditions / take_profit / stop_loss), `size_pct ∈ (0, 1]`,
  positive TP/SL when present, finite-Decimal `Condition.rhs`,
  `period ∈ [1, 500]`. Warm-up-vs-timeframe heuristic deferred to 2A+1
  (no principled line between legit long-lookback and config typo).
- Reuses `domain.value_objects.Timeframe`, `domain.venues.VenueId`,
  `domain.symbols.Symbol` (no parallel enums).
- 40 unit tests covering happy path, invariants, immutability,
  `model_copy(update=...)` cloning, builder/constructor parity.
- No MCP surface (2D), no persistence (2E), no backtest execution (2B) —
  StrategySpec is a pure DTO at this layer.

### Added — Phase 2C — Post-backtest analytics Visitor pattern

- `BacktestReport` DTO (`BacktestTrade` + `EquityPoint` + `TradeSide`) with
  chronological + positive-value invariants; `ValidationError` on bad input.
- `BacktestVisitor` Protocol (`runtime_checkable`, generic over return type)
  + 5 concrete visitors:
  - `TotalReturnVisitor` → `Decimal`
  - `WinRateVisitor` → `Decimal` in `[0, 1]`
  - `ProfitFactorVisitor` → `Decimal | None` (`None` when gross loss is zero)
  - `MaxDrawdownVisitor` → `Decimal` in `[0, 1]`
  - `SharpeRatioVisitor` → `Decimal` (configurable `annualisation_factor`
    and `risk_free_rate`)
- `BacktestAnalyticsService` composer — preserves visitor order, rejects
  duplicate visitor names at construction, propagates visitor exceptions.
- Hypothesis property-based tests for `MaxDrawdownVisitor`
  (monotone-increasing curve → 0, range `[0, 1]` always) and
  `SharpeRatioVisitor` (finiteness on bounded curves).
- +38 unit tests, all green.

## [0.3.1] - 2026-04-22 — **Phase 1.5 verification follow-up**

Full semantic-invariant sweep of the v0.3.0 surface surfaced 19 issues
across the review-toolkit agents (code / tests / comments / silent-
failures / type-design). All 6 Critical + 8 Important + 5 Suggestion +
17 coverage gaps addressed; PR #1 merged into main.

### Fixed — Phase 1.5 follow-up

- **`get_trades` now works end-to-end**: `CCXTProvider` overrides
  `_fetch_trades_raw` / `_normalize_trades` on top of a new
  `CCXTAdapter.trades_to_domain`. Previously fell through to
  `BaseProvider`'s `NotImplementedError("trades not implemented for
  this provider")`.
- **KuCoin order-book depth normalisation**: `CCXTProvider._snap_order_book_depth`
  collapses any requested depth to `{20, 100}` (the only values CCXT
  accepts for `kucoin.fetchOrderBook`). Previously a live call with
  `depth=5` or `depth=50` failed with
  `kucoin fetchOrderBook() limit argument must be 20 or 100`.
- **Version drift resolved**: `pyproject.toml`, `src/cryptozavr/__init__.py`,
  `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` all bumped
  to `0.3.0` to match the git tag and CHANGELOG. Tests now read
  `cryptozavr.__version__` instead of hard-coding the literal.
- **`cryptozavr://categories` resource fixed**: `CoinGeckoAdapter.categories_to_list`
  now copies `id` into `category_id` so `CategoryDTO.from_provider` stops raising
  `KeyError` against the current `/coins/categories` response shape. Previously
  surfaced as a generic "Error reading resource" (`mask_error_details=True`).
- **Uniform `application/json` MIME on all resources**: every resource now
  returns `ResourceResult(ResourceContent(content=json.dumps(...),
  mime_type="application/json"))` per FastMCP v3 `servers/resources.mdx`
  §ResourceResult. Previously `cryptozavr://symbols/{venue}` was served as
  `text/plain` because FastMCP drops the decorator-level `mime_type` hint
  for URI-template resources; clients can now render the JSON payload
  natively instead of as an escaped string.

### Added — catalog tools with `structuredContent`

Resource wire format forces `TextResourceContents.text=str`, so any nested
JSON surfaces with escaped quotes (`\"`) in the raw client view. We added
Pydantic-DTO tool equivalents so FastMCP v3 auto-populates
`CallToolResult.structuredContent` — clients render native JSON objects:

- `list_venues() -> VenuesListDTO`
- `list_symbols(venue) -> SymbolsListDTO`
- `list_trending() -> TrendingListDTO`
- `list_categories() -> CategoriesListDTO`
- `get_venue_health() -> VenueHealthDTO`

Resources stay in place for cacheable / URI-template semantics; the tools
are the clean-render alternative for interactive views.

### Tests
- +14 unit tests: `trades_to_domain` (4), provider trades happy-path +
  unknown-side (2), order-book depth snap parametrised over 6 inputs,
  CoinGecko categories id→category_id mapping + legacy preservation (2).
- Unit + contract total: **473 passing** (was 423).

### Review-driven hardening — Important + Suggestion items

**Semantic correctness**
- `HealthMonitor.mark_probe_performed()` now fires **after** the probe
  completes, not before — a hung probe can no longer masquerade as
  "just checked" in `cryptozavr://venue_health`.
- `TickerSyncWorker.sync_once` fan-out moved from serial-per-subscription
  to `asyncio.gather(..., return_exceptions=True)`. `CancelledError`
  is re-raised; other exceptions are logged with `exc_info`.
- `VenueState.mark_probe_performed` is now monotonic — an older
  timestamp cannot regress the observable last-seen time.

**Type invariants**
- `_HistogramStats` rejects unsorted buckets or missing `+inf` at the
  top; `MetricsRegistry.__init__` validates up-front.
- `TickerSubscription.channel_id` is validated against
  `TickerSubscription.make_channel_id(venue_id, symbol)` in `__post_init__`
  so arbitrary channel strings can no longer leak the abstraction.
- `SymbolsListDTO` / `TrendingListDTO` / `CategoriesListDTO` added a
  `success-xor-error` model validator — non-empty list + non-null
  `error` is no longer representable.
- `VenueHealthDTO.venues` now enforces venue uniqueness via
  `@model_validator`.
- `CategoryDTO.from_provider` falls back safely to `category_id` or
  `"unknown"` when `name` is absent.

**Silent-failure reduction**
- `except Exception` branches in `bootstrap._start_background_services`,
  `_shutdown`, `HealthMonitor._run_probe`, and
  `cryptozavr://trending` / `cryptozavr://categories` resources now use
  `logger.exception` for full stack traces, and sanitise exception
  detail leakage (`str(exc)` → `f"{type(exc).__name__}: upstream unavailable"`).

**Docs**
- README.md slash-command list aligned to actual 8 commands.
- `cryptozavr://trending` description clarifies `rank` is a synthetic
  0-indexed position in the CoinGecko response, not a trading rank.

**Tests added for previously-untested invariants**
- `test_mark_probe_performed_fires_after_probe_completes`
- `test_sync_once_runs_subscriptions_concurrently` +
  `test_sync_once_propagates_cancellation`
- `test_run_forever_survives_iteration_exception`
- `test_mark_probe_performed_is_monotonic`
- `test_rejects_unsorted_buckets` + `test_rejects_missing_inf_bucket`
- `test_fetch_trades_forwards_since_as_ms`
- `test_on_ticker_change_extracts_venue_from_record_venue_alias` +
  `test_on_ticker_change_extracts_venue_from_data_key` +
  `test_on_ticker_change_extracts_top_level_venue_id`
- `test_no_clip_code_when_chunk_already_fits`
- `test_each_endpoint_label_emitted` (parametrised × 5 endpoints)
- `TestListDTOValidators` (6 tests covering DTO XOR-validators)

## [0.3.0] - 2026-04-22 — **Phase 1.5: Realtime + Observability**

Ships the observability substrate and realtime-driven cache invalidation that
Phase 2 trading logic will depend on.

**Infrastructure**
- `MetricsRegistry` — thread-safe in-memory Prometheus-compatible registry.
  Counters + cumulative-bucket histograms with Prometheus "le" semantics.
  `snapshot()` returns a JSON-serialisable dict ready for a future text
  exporter.
- `MetricsDecorator` — 5th decorator in the provider chain. Classifies every
  call as `ok` / `rate_limited` / `timeout` / `error`, emits
  `provider_calls_total{venue,endpoint,outcome}` and
  `provider_call_duration_ms{venue,endpoint}` with buckets
  `[50, 100, 250, 500, 1000, 2500, 5000, +Inf]` ms.
- `ProviderFactory.metrics_registry` — threads a single registry into the
  decorator chain (Logging > Caching > RateLimit > Retry > Metrics > base).
- `InMemoryCachingDecorator.invalidate_tickers()` — targeted eviction of
  ticker cache keys; leaves OHLCV / order book buckets untouched.
- `RealtimeSubscriber.subscribe_ticker(venue, symbol, callback)` +
  `subscriptions()` accessor — per-symbol tracking so background workers
  can enumerate the live set. Legacy `subscribe_tickers(venue)` still works.

**Application**
- `HealthMonitor` — periodic probe loop (default 60s). For each
  `VenueId`, runs the supplied `HealthProbe`, updates `VenueState`
  through `on_request_succeeded` / `on_request_failed` and emits
  `venue_health_check_total{venue,outcome}`. Idempotent start/stop.
- `VenueState.last_checked_at_ms` + `mark_probe_performed(now_ms)` —
  consumed by the new resource to render `last_checked_ms`.
- `TickerSyncWorker` — background asyncio task (default 30s). Reads
  `RealtimeSubscriber.subscriptions()` and force-refreshes every ticker
  through `TickerService`. No-op when there are no subscriptions.
- `CacheInvalidator` — routes Supabase Realtime `tickers_live` row
  changes to `providers[venue].invalidate_tickers()`. Exposes
  `start()` that opens subscribe_tickers channels per venue; failures
  are logged, not raised.

**MCP surface**
- Resource `cryptozavr://venue_health` — JSON `{venues: [{venue, state,
  last_checked_ms}]}`. `state` is `healthy` / `degraded` / `down`
  (RATE_LIMITED collapses into `degraded`).
- `/cryptozavr:health` command now also reads this resource and reports
  per-venue state + last_checked_ms alongside the echo reachability
  check.

**Lifespan wiring**
- `build_production_service` assembles MetricsRegistry → HealthMonitor →
  TickerSyncWorker → CacheInvalidator and starts them inside the
  lifespan. Start failures are logged per-service so the MCP subprocess
  still boots when Supabase Realtime is offline. Cleanup stops the
  background services first (cache invalidator → ticker sync → health
  monitor) before tearing HTTP / gateway / pg pool.
- New `LIFESPAN_KEYS`: `metrics_registry`, `health_monitor`,
  `ticker_sync_worker`, `cache_invalidator`, `venue_states`.

**Plugin surface additions**
- SessionStart banner now points at `cryptozavr://venue_health`.
- Skills: `venue-debug` (walks the 5-layer chain to pinpoint whether a
  venue failure is cache staleness, rate limiting, transport or upstream
  downtime) and `post-session-reflection` (3-bullet produced / decided /
  next wrap-up).

### Tests
- +50 unit tests: MetricsRegistry 5 / MetricsDecorator 7 /
  HealthMonitor 9 / RealtimeSubscriber 3 / TickerSyncWorker 5 /
  CacheInvalidator 8 / venue_health resource 5 / cache invalidation 2 /
  VenueState probe timestamp 2 / ProviderFactory metrics 1 /
  plus extended test_analytics_service import hoist.
- Unit + contract total: **423 passing** (was 373).

### Commits (atomic on `feat/phase-1.5-ralph`)
- `feat(infrastructure): add MetricsDecorator (Prometheus counters/histograms)`
- `feat(application): add HealthMonitor service`
- `feat(infrastructure): add per-symbol subscribe_ticker to RealtimeSubscriber`
- `feat(application): add TickerSyncWorker background task`
- `feat(mcp): add cryptozavr://venue_health resource`
- `feat(infrastructure): invalidate ticker cache on realtime tickers_live updates`
- `feat(plugin): extend SessionStart banner with venue_health hint`
- `feat(plugin): add venue-debug + post-session-reflection skills`
- `feat(mcp): wire observability background services into lifespan`
- `docs(plugin): /cryptozavr:health also reads cryptozavr://venue_health`

## [0.2.0] - 2026-04-22 — **MVP closure**

### Added — M3.4 History streaming + SessionExplainer

Closes the MVP tool surface and ships the canonical `{data, quality, reasoning}` envelope from the spec.

**Services (L4)**
- `OHLCVPaginator` — Iterator-pattern async iterator over `[since_ms, until_ms)`. Walks the window in `chunk_size` candle steps via `OhlcvService.fetch_ohlcv`, advancing the cursor by `last_opened_at + timeframe_ms`. Short-circuits on empty chunks and has a safety guard against no-progress cursors. `total_chunks_estimate()` helper drives progress UX.

**Envelope helper**
- `src/cryptozavr/mcp/explainer.py::build_envelope(data, quality, reason_codes, query_id, notes)` — stateless wrapper around tool output. Pydantic BaseModels dump via `model_dump(mode="json")`; dicts pass through. Auto-generates a 12-char `query_id` when unset. Existing tools (ticker/ohlcv/etc.) untouched — only `fetch_ohlcv_history` opts into the envelope; others can migrate later if desired.

**DTOs**
- `OHLCVHistoryDTO` — wire format for streamed history (venue / symbol / timeframe / range / candles / chunks_fetched / reason_codes). Decimal-safe via `model_dump(mode="json")`.

**MCP surface**
- Tool: `fetch_ohlcv_history(venue, symbol, timeframe, since_ms, until_ms, chunk_size=500, force_refresh=False)` → envelope `{data: OHLCVHistoryDTO, quality, reasoning}`. Iterates the paginator, calls `ctx.report_progress(chunk_n, total_est, msg)` between each fetch, captures latest quality. `timeout=180s`, `meta={mode: history, version}`. Inverted ranges and unknown timeframes surface as `ToolError` via `domain_to_tool_error`.

**Slash commands**
- `/cryptozavr:history <venue> <symbol> <timeframe> <since_ms> <until_ms> [chunk_size]` — drives streaming with a Window / Price action / Quality / Provenance layout.
- `/cryptozavr:health` banner lists all 11 tools.

**Plugin surface (final MVP)**
- **Tools (11)**: echo, get_ticker, get_ohlcv, get_order_book, get_trades, resolve_symbol, compute_vwap, identify_support_resistance, volatility_regime, analyze_snapshot, **fetch_ohlcv_history**
- **Prompts (2)**: research_symbol, risk_check
- **Resources (4)**: cryptozavr://venues, ://symbols/{venue}, ://trending, ://categories
- **Slash commands (8)**: health, ticker, ohlcv, research, resolve, trending, analyze, **history**

### Tests
- +21 unit tests (OHLCVPaginator 7, OHLCVHistoryDTO 2, SessionExplainer 5, fetch_ohlcv_history 6, server startup +1)
- Unit total: **370** (was 349 after M3.3)
- Grand total: 370 unit + 5 contract + 14 live integration = **389**

### Commits
- `feat(application): add OHLCVPaginator iterator for history streaming` (5861147)
- `feat(mcp): add OHLCVHistoryDTO for streamed history` (0809040)
- `feat(mcp): add SessionExplainer envelope helper` (3028f41)
- `feat(mcp): add fetch_ohlcv_history tool (streaming + envelope)` (5597174)
- `feat(mcp): wire fetch_ohlcv_history into server + /history command` (a4e7b70)

---

**MVP scope closed.** All 17 GoF patterns from the spec are in code (Strategy, Template Method, Adapter, Bridge, Decorator×4, Chain of Responsibility×5, State, Factory Method, Singleton via DI, Flyweight, Facade, Iterator, plus the SessionExplainer envelope). Next milestones (phase 2+) live outside MVP scope: Builder for `StrategySpec`, Visitor for backtest analytics, Memento for decision replay, background tasks via `task_meta`.

## [0.1.4] - 2026-04-22

### Added — M3.3 Analytics MCP tools

Wraps M3.1's MarketAnalyzer strategies as MCP tools so Claude/Codex/etc. can pull computed market views, not just raw data.

**Services (L4)**
- `AnalyticsService` — thin orchestrator that chains `OhlcvService.fetch_ohlcv()` into `MarketAnalyzer.analyze()`. Returns `(AnalysisReport, reason_codes)` so the OHLCV audit trail propagates all the way to the MCP response.

**DTOs**
- `AnalysisResultDTO` — wire format for a single `AnalysisResult` (strategy / confidence / findings / reason_codes). `_json_friendly` helper recursively converts tuples → lists so Decimal-in-tuple findings (S/R levels) serialise cleanly via `model_dump(mode="json")`.
- `AnalysisReportDTO` — composite report (venue / symbol / timeframe / results list / reason_codes).

**MCP surface**
- Tool: `compute_vwap(venue, symbol, timeframe, limit=200, force_refresh=False)` → `AnalysisResultDTO`. `timeout=30s`, `meta={strategy: vwap, version}`.
- Tool: `identify_support_resistance(...)` → `AnalysisResultDTO`. Swing-based pivots + clustering.
- Tool: `volatility_regime(...)` → `AnalysisResultDTO`. ATR classifier (calm/normal/high/extreme).
- Tool: `analyze_snapshot(...)` → `AnalysisReportDTO`. Composite: one OHLCV fetch, 3 strategies, emits `ctx.report_progress(step, total, msg)` for each strategy. `timeout=60s`.
- All tools: idiomatic v3 — `Depends(get_analytics_service)`, module-level singleton, `ctx.info/warning` for reason_codes + staleness, `ToolError` via `domain_to_tool_error`.

**Slash commands**
- `/cryptozavr:analyze <venue> <symbol> [timeframe] [limit]` — drives the composite `analyze_snapshot` tool and renders a fair-value / levels / volatility / provenance layout.
- `/cryptozavr:health` banner updated to list all 10 tools.

**Plugin surface now**
- **Tools (10)**: echo, get_ticker, get_ohlcv, get_order_book, get_trades, resolve_symbol, **compute_vwap**, **identify_support_resistance**, **volatility_regime**, **analyze_snapshot**
- **Prompts (2)**: research_symbol, risk_check
- **Resources (4)**: cryptozavr://venues, ://symbols/{venue}, ://trending, ://categories
- **Slash commands (7)**: health, ticker, ohlcv, research, resolve, trending, **analyze**

### Tests
- +20 unit tests (DTOs, AnalyticsService, 4 analytics tools, wire smoke test)
- Unit total: 349 (was 332 after M3.2)

### Docs
- `CLAUDE.md`: new "Editing workflow — import placement" section — pre-commit/formatter strips unreferenced imports between Edits; document the safe ordering (import with usage, never ahead).

### Commits
- `feat(mcp): add AnalysisResultDTO + AnalysisReportDTO` (54f617f)
- `feat(application): add AnalyticsService L4 orchestrator` (ac78319)
- `feat(mcp): add 3 single-strategy analytics tools` (0dc4d04)
- `feat(mcp): add analyze_snapshot composite analytics tool` (c239d79)
- `feat(mcp): wire analytics stack into bootstrap + server` (c57df34)
- `docs(claude): add import-placement rule for formatter safety` (452cbd9)

## [0.1.3] - 2026-04-22

### Added — M3.2 Discovery surface

Built on top of the idiomatic M3.0 foundation (Depends DI + dict lifespan + ctx logging).

**Services (L4)**
- `SymbolResolver` — in-memory fuzzy user-input → Symbol. 3-step cascade: direct native_symbol hit → format variants (separator permutations + concatenated-form split on known quotes) → base-only lookup with default quotes (USDT/USD/BTC/ETH). Unknown venue → `VenueNotSupportedError`; nothing matched → `SymbolNotFoundError`.
- `DiscoveryService` — thin facade over `CoinGeckoProvider.list_trending` + `list_categories` (decorated by Retry/RateLimit/Caching/Logging under the hood).

**MCP surface**
- Tool: `resolve_symbol(user_input, venue)` → `SymbolDTO`. Uses `Depends(get_symbol_resolver)` + `ctx.info` logging.
- Resource: `cryptozavr://trending` — trending assets (CoinGecko). `idempotentHint=false` (rank shifts ~every 10min upstream).
- Resource: `cryptozavr://categories` — category market cap + 24h change. `idempotentHint=true`.
- Graceful degradation: upstream CoinGecko errors return `{"assets": [], "error": "..."}` payloads instead of crashing the resource read.

**Plugin surface now**
- **Tools (6)**: echo, get_ticker, get_ohlcv, get_order_book, get_trades, **resolve_symbol**
- **Prompts (2)**: research_symbol, risk_check
- **Resources (4)**: cryptozavr://venues, ://symbols/{venue}, **://trending**, **://categories**

**Slash commands + banner**
- `/cryptozavr:resolve <user_input> [venue]` — wraps resolve_symbol tool.
- `/cryptozavr:trending` — reads both discovery resources, renders two compact tables.
- SessionStart banner updated: 6 commands + 2 prompts + 4 resources + 6 tools enumerated.

### Tests

- `test_symbol_resolver.py` (7), `test_discovery_service.py` (3), `test_get_symbol_tool.py` (2), extended `test_resources.py` (+3). **15 new unit tests.**
- Total: **337 unit + 5 contract + 14 integration (skip-safe)**.

### Next

- **M3.3**: Analytics MCP tools wrapping MarketAnalyzer (VWAP, Support/Resistance, VolatilityRegime) as `compute_vwap`, `identify_support_resistance`, `volatility_regime`, plus composite `analyze_snapshot`.
- **M3.4**: `fetch_ohlcv_history` streaming + SessionExplainer envelope → tag v0.2.0 (MVP closure).

## [0.1.2] - 2026-04-22

### Refactored — M3.0 FastMCP v3 idiomatic cleanup

Five anti-patterns fixed (discovered during M3.2 pause; user flagged non-idiomatic v3 usage before propagation):

- **Lifespan yields a `dict`**, not a dataclass. `FastMCP[AppState]` generic + `cast(Any, ctx.lifespan_context).attr` pattern removed. New module `src/cryptozavr/mcp/lifespan_state.py` with `LIFESPAN_KEYS` constants + 8 typed `Depends` accessors.
- **`Depends(get_xxx_service)` injection** across all 4 market-data tools (get_ticker, get_ohlcv, get_order_book, get_trades). Dependency params hidden from MCP schema; services resolved at tool-call time per FastMCP v3 DI contract.
- **`ctx.info` / `ctx.warning` logging** per tool call. Surfaces reason_codes, cache:write_failed, and non-fresh staleness warnings to MCP clients alongside the structured response.
- **`FastMCP(mask_error_details=True)`** — non-ToolError exceptions no longer leak stack traces to clients.
- 4 test files updated: `_AppState` dataclass fixtures replaced by dict-yielding lifespan with `LIFESPAN_KEYS`.

### Added — prompts + catalog resources

- `@mcp.prompt research_symbol(venue, symbol)` — 4-tool parallel research template (Price → Trend → Liquidity → Flow → Provenance).
- `@mcp.prompt risk_check(venue, symbol)` — data-quality-first pre-decision check with PASS/DEGRADED/FAIL verdict based on staleness, spread, and tape imbalance.
- `@mcp.resource cryptozavr://venues` — enumerated venue list (application/json).
- `@mcp.resource cryptozavr://symbols/{venue}` — symbols-per-venue catalog. Unknown venue returns `{"error": "unsupported"}` payload (not an exception).
- `SymbolRegistry.all_for_venue()` — stable-sorted enumeration helper.

### Tests

- `test_lifespan_state.py`, `test_prompts.py`, `test_resources.py` — 9 new tests.
- 4 existing tool-test files updated to dict-yield lifespan.
- Total **322 unit + 5 contract + 14 integration (skip-safe)**.

### Plugin surface

- **Tools**: 5 (echo + 4 market-data)
- **Prompts**: 2 (research_symbol, risk_check) — cross-client portable
- **Resources**: 2 (venues + symbols/{venue}) — client-cacheable

### Next

- **M3.2** (resumed): `SymbolResolver` + `DiscoveryService` + discovery tools (resolve_symbol) + discovery resources (trending, categories) — now built on the idiomatic foundation.
- **M3.3**: analytics MCP tools on top of MarketAnalyzer.
- **M3.4**: fetch_ohlcv_history streaming + SessionExplainer envelope → tag v0.2.0 (MVP closure).

## [0.1.1] - 2026-04-22

### Added — M3.1 MarketAnalyzer (Strategy pattern)
- `AnalysisStrategy` Protocol (runtime_checkable) + `AnalysisResult` dataclass (strategy name, typed-dict findings, Confidence). Per MVP spec §5.
- `VwapStrategy` — Volume-Weighted Average Price via typical (h+l+c)/3 × volume. Zero-volume bars counted in bars_used but skipped in the weighted sum. 5 unit tests.
- `SupportResistanceStrategy` — swing-pivot SR detector with level clustering (default window=2, cluster_pct=0.5). 4 unit tests.
- `VolatilityRegimeStrategy` — ATR-based regime classifier (calm/normal/high/extreme bands on ATR-as-%-of-close). Default window=14. 5 unit tests.
- `MarketAnalyzer` Strategy context — dispatches to strategy registry by name, preserves caller-requested order, wraps results in `AnalysisReport` (symbol + timeframe + tuple[AnalysisResult]). 3 unit tests.
- 20 new unit tests. Total 308 unit + 5 contract + 14 integration (skip-safe).

### Next
- M3.2: Discovery tools (resolve_symbol, list_symbols, list_categories, scan_trending) — 4 new MCP tools + SymbolResolver service.
- M3.3: Analytics MCP tools on top of MarketAnalyzer (analyze_snapshot, compute_vwap, identify_support_resistance, volatility_regime).
- M3.4: fetch_ohlcv_history streaming + SessionExplainer envelope + /cryptozavr:scan/analyze commands → tag v0.2.0 (MVP closure).

## [0.1.0] - 2026-04-22

### Added — M2.8 Production-ready multi-platform plugin

**Plugin manifest**
- `.claude-plugin/plugin.json` (name, version, author, keywords, MIT).
- `.claude-plugin/marketplace.json` — self-hosted marketplace registry with `source: "./"` (mirrors dj-music-plugin / exa-mcp-server convention). Users install via `/plugin marketplace add https://github.com/evgenygurin/cryptozavr`.

**Slash commands (4)**
- `/cryptozavr:ticker <venue> <symbol>` — wraps get_ticker
- `/cryptozavr:ohlcv <venue> <symbol> <timeframe> [limit]` — OHLCV candles
- `/cryptozavr:research <venue> <symbol>` — 4-tool parallel research collage (Price → Trend → Liquidity → Flow → Provenance)
- `/cryptozavr:health` — echo smoke test

**Agent (1)**
- `crypto-researcher` — subagent (model=sonnet, color=cyan). Strict "data, not advice" rails. Tool list restricted to the 4 cryptozavr MCP tools. Structured Price → Trend → Liquidity → Flow → Provenance report format.

**Skills (2)**
- `crypto-research` — when-to-invoke guide + tool-selection matrix + research rails.
- `interpreting-market-data` — field-by-field legend covering ticker/OHLCV/order_book/trades + 5-handler reason_codes taxonomy + red flags.

**Hooks**
- `SessionStart` hook prints a plugin loaded banner on startup only (not on clear/compact). Uses `${CLAUDE_PLUGIN_ROOT}` for path portability.

**Cross-platform**
- `.codex/README.md`, `.opencode/README.md`, `.cursor-plugin/README.md` — per-platform install + feature-parity notes.
- `gemini-extension.json` — Gemini CLI manifest (same MCP server).
- `docs/README.claude-code.md` / `docs/README.codex.md` / `docs/README.opencode.md` — install guides.

**Docs**
- `README.md` rewritten for plugin users (not just developers).
- `.env.example` with inline comments on allowed values.
- `docs/superpowers/m2.8-smoke-test.md` — plugin-validator findings + install verification steps.

### Fixed
- Removed M1-legacy root `plugin.json` (duplicated `.claude-plugin/plugin.json` with stale version 0.0.1).
- `tests/unit/mcp/test_settings.py::test_settings_missing_required_field` now passes `_env_file=None` so the local `.env` (populated for cloud Supabase) doesn't mask the "missing var → ValidationError" assertion.

### Next
- M3: L4 business logic — signals (crossover, divergence, RSI), triggers, alerts. Elicit-based approval flows for trading ops (later phase).

## [0.0.10] - 2026-04-21

### Added — M2.7 Realtime subscriber + cloud Supabase
- Cloud Supabase project `midoijmwnzyptnnqqdws` (eu-west-1, Postgres 17) provisioned. All 7 migrations applied: extensions, reference, market_data, audit, rls, cron, realtime. Seed data (kucoin + coingecko venues) loaded. Completes M2.2 Task 9 (deferred for 5 milestones — now done).
- `supabase/migrations/00000000000060_realtime.sql` — adds `cryptozavr.tickers_live` to the `supabase_realtime` publication. Other market-data tables excluded (batch writes would flood subscribers).
- `RealtimeSubscriber` (replaces M2.2 stub): real `supabase-py` AsyncClient wrapper. `subscribe_tickers(venue_id, callback)` opens one channel per venue filtered by `venue_id=eq.<venue>`, streams INSERT/UPDATE/DELETE payloads. `close()` unsubscribes all channels and tears down the connection (best-effort — per-channel failures don't block the rest).
- `AppState` now carries `subscriber: RealtimeSubscriber` alongside the four market-data services. `build_production_service` returns a 6-tuple. Lifespan cleanup closes the subscriber FIRST, before http/gateway/pg_pool — prevents websocket callbacks firing against closed connections.
- Infrastructure: `pyproject.toml` + `.pre-commit-config.yaml` updated so `mypy` resolves `supabase` imports under both local and pre-commit venv.
- 5 new unit tests (mocked AsyncClient + channel). 1 new integration test (`tests/integration/supabase/test_realtime_live.py`) — skip-safe when cloud env vars absent.
- Total: 288 unit + 5 contract + 3 integration (skip-safe).

### Deferred to M3+
- MCP tool for realtime (`subscribe_ticker` as streaming tool) — needs FastMCP background task + notification plumbing. Phase 2 scope.
- `.env` + live integration verification — requires user-provided DB password and service_role_key (dashboard secrets, not accessible via MCP).

### Next
- M3: L4 business logic — signals, triggers, alerts. Elicit-based approval flows for trading ops (later phase).

## [0.0.9] - 2026-04-21

### Added — M2.6 `get_order_book` + `get_trades` tools
- `PriceSizeDTO` (bid/ask level), `OrderBookDTO` (bids/asks arrays + spread/spread_bps), `TradeTickDTO` (single trade), `TradesDTO` (wrapped list + venue/symbol). All Pydantic v2 frozen BaseModels with `from_domain` factories.
- `OrderBookService` (L4) — non-cached fetch via `build_order_book_chain`. `fetch_order_book(venue, symbol, depth, force_refresh)` returns `OrderBookFetchResult(snapshot, reason_codes)`.
- `TradesService` (L4) — non-cached fetch via `build_trades_chain`. `fetch_trades(venue, symbol, limit, since, force_refresh)` returns `TradesFetchResult(venue, symbol, trades, reason_codes)`.
- `build_order_book_chain` / `build_trades_chain` assembly helpers (delegate to `_build_chain`).
- `register_order_book_tool(mcp)`: `get_order_book(venue, symbol, depth, force_refresh)` bounded `depth` 1..200. `annotations.idempotentHint=False` (book ticks).
- `register_trades_tool(mcp)`: `get_trades(venue, symbol, limit, force_refresh)` bounded `limit` 1..1000. `annotations.idempotentHint=False`.
- `AppState` now carries all four services (ticker, ohlcv, order_book, trades). `build_production_service` returns a 5-tuple.
- ~16 new unit tests (DTOs 7 + OrderBookService 5 + TradesService 5 + each tool 3). Total 283 unit + 5 contract + 2 integration (skip-safe).

### Next
- M2.7+: Realtime subscriber (phase 1.5), signals/triggers (L4 business logic), production deployment to cloud Supabase.

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
