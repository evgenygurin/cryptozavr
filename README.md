# cryptozavr

Risk-first crypto market research plugin for Claude Code, OpenAI Codex, OpenCode, Cursor, and Gemini CLI. 16 MCP tools over KuCoin and CoinGecko with Supabase-backed cache, realtime cache invalidation, observability, provenance tracking, and auditable reasoning.

## What's in the box

**MCP tools (16)**

*Market data (5)*
- `get_ticker(venue, symbol, force_refresh)` — last / bid / ask / 24h stats
- `get_ohlcv(venue, symbol, timeframe, limit, force_refresh)` — OHLCV candles (1m..1w)
- `get_order_book(venue, symbol, depth, force_refresh)` — bids / asks / spread_bps; KuCoin `depth` snaps to `{20, 100}`
- `get_trades(venue, symbol, limit, force_refresh)` — recent trade ticks
- `resolve_symbol(user_input, venue)` — fuzzy symbol resolution

*Analytics (4) + history (1)*
- `compute_vwap(...)` — VWAP + bars_used + confidence
- `identify_support_resistance(...)` — swing-pivot S/R + `pivots_found` + cluster means
- `volatility_regime(...)` — ATR-based classifier (calm/normal/high/extreme)
- `analyze_snapshot(...)` — composite VWAP + S/R + volatility with one OHLCV fetch
- `fetch_ohlcv_history(...)` — streaming history with `paginator:clipped_to_window` guarantee

*Catalog (5, `structuredContent` — no escape)*
- `list_venues`, `list_symbols(venue)`, `list_trending`, `list_categories`, `get_venue_health`

*Plus `echo` for smoke.*

**MCP resources (4 + 1 URI-template)**
- `cryptozavr://venues`, `cryptozavr://symbols/{venue}`, `cryptozavr://trending`, `cryptozavr://categories`, `cryptozavr://venue_health`

**MCP prompts (2, cross-client portable)**
- `research_symbol(venue, symbol)` — 4-tool parallel research template
- `risk_check(venue, symbol)` — data-quality pre-decision check

**Slash commands (8)**
- `/cryptozavr:ticker`, `/cryptozavr:ohlcv`, `/cryptozavr:order_book` (via research), `/cryptozavr:trades` (via research), `/cryptozavr:research`, `/cryptozavr:resolve`, `/cryptozavr:trending`, `/cryptozavr:analyze`, `/cryptozavr:history`, `/cryptozavr:health`

**Subagent**
- `crypto-researcher` — multi-step market research specialist (calm, explainable, no advice)

**Skills (4)**
- `crypto-research` — when-to-invoke + tool-selection matrix
- `interpreting-market-data` — field-by-field legend + red flags
- `venue-debug` — walk the 5-layer L2 chain to pinpoint failures
- `post-session-reflection` — disciplined 3-bullet wrap-up (produced / decided / next)

**SessionStart hook** — prints a plugin-loaded banner with command cheat-sheet and venue health pointer.

**Every response carries**
- `reason_codes` audit trail (5-handler chain: `venue → symbol → cache → provider`; plus `paginator:clipped_to_window` for streamed history)
- `staleness` + `cache_hit` — so you always know if data is fresh
- For catalog & analytics tools — `structuredContent` in the MCP response (no escaped JSON strings)

## Install

Pick your platform:
- [Claude Code](docs/README.claude-code.md)
- [OpenAI Codex](docs/README.codex.md)
- [OpenCode](docs/README.opencode.md)
- [Cursor](.cursor-plugin/README.md)
- [Gemini CLI](gemini-extension.json) — wired via the same mcpServers config

## Env setup

Copy `.env.example` → `.env` and fill:
- `SUPABASE_URL` — your Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` — from Dashboard → API Keys → `service_role`
- `SUPABASE_DB_URL` — PostgreSQL connection string (session pooler, port 5432)

The cryptozavr MCP server needs Python 3.12 + `uv`. Install with:

    uv sync --all-extras

## Philosophy

1. **Risk-first, not signal-first.** Audit trail + provenance before prediction.
2. **Calm execution.** Dispassionate, institutional-minded. No FOMO.
3. **Declarative over ad-hoc.** Settings, thresholds, rate limits in config, not prompts.
4. **Explainability and auditability.** Every answer contains `data`, `quality`, `reasoning`.
5. **Safe agent design.** LLM proposes; human approves; deterministic code executes.

See [docs/superpowers/specs/2026-04-21-cryptozavr-mvp-design.md](docs/superpowers/specs/2026-04-21-cryptozavr-mvp-design.md) for the full MVP design.

## Architecture

- **Domain (L3)** — `src/cryptozavr/domain/`: frozen dataclasses (Ticker, OHLCVSeries, OrderBookSnapshot, TradeTick) + DataQuality envelope.
- **Infrastructure (L2)** — `src/cryptozavr/infrastructure/`: CCXT adapter (KuCoin) with `trades_to_domain` + `_snap_order_book_depth`, CoinGecko HTTP client with `id→category_id` mapping, Supabase gateway (asyncpg + supabase-py realtime), **5 decorators** (Retry / RateLimit / InMemoryCache / Logging / Metrics), 5-handler chain of responsibility, `MetricsRegistry` (Prometheus-compatible counters + cumulative histograms).
- **Application (L4)** — `src/cryptozavr/application/services/`: `TickerService`, `OhlcvService`, `OrderBookService`, `TradesService`, `AnalyticsService`, `SymbolResolver`, `DiscoveryService`, plus `HealthMonitor` + `TickerSyncWorker` + `CacheInvalidator` (async tasks started from lifespan).
- **MCP (L5)** — `src/cryptozavr/mcp/`: FastMCP v3 server with dict-lifespan, 16 tools, 4 + 1-template resources, 2 prompts, `cryptozavr://venue_health` observability endpoint.

**15 GoF patterns** applied: Template Method, Adapter, Bridge, **Decorator (5 layered, incl. MetricsDecorator)**, Chain of Responsibility (5 handlers), State (venue health), Factory Method, Singleton via DI, Flyweight (SymbolRegistry), Facade (SupabaseGateway), Iterator (OHLCVPaginator), Strategy (MarketAnalyzer), plus **Observer** (Supabase Realtime → `CacheInvalidator`).

## Tests

    uv run pytest tests/unit tests/contract -m "not integration"   # 440 unit + contract, ~4s
    uv run pytest tests/integration                                 # 14 live tests, ~40s (needs .env)

## Status

**v0.3.0** — MVP + Phase 1.5 (Realtime + Observability) shipped. `MetricsRegistry`, `HealthMonitor`, `TickerSyncWorker`, `CacheInvalidator`, `venue_health` resource + 5 catalog tools with `structuredContent`. Next: Phase 2 — signals / triggers / alerts with Elicit-based approval flows.

## License

MIT — see [LICENSE](LICENSE).
