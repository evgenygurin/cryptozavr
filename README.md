# cryptozavr

Risk-first crypto market research plugin for Claude Code, OpenAI Codex, OpenCode, Cursor, and Gemini CLI. Provides 4 MCP tools over KuCoin and CoinGecko with Supabase-backed cache, provenance tracking, and auditable reasoning.

## What's in the box

**MCP tools**
- `get_ticker(venue, symbol, force_refresh)` — last price + bid/ask + 24h stats
- `get_ohlcv(venue, symbol, timeframe, limit, force_refresh)` — OHLCV candles (1m..1w)
- `get_order_book(venue, symbol, depth, force_refresh)` — bids/asks + spread_bps
- `get_trades(venue, symbol, limit, force_refresh)` — recent trade ticks

**Slash commands**
- `/cryptozavr:ticker <venue> <symbol>`
- `/cryptozavr:ohlcv <venue> <symbol> <timeframe>`
- `/cryptozavr:research <venue> <symbol>` (4-tool parallel collage)
- `/cryptozavr:health` (smoke test)

**Subagent**
- `crypto-researcher` — specialist for multi-step market research (calm, explainable, no advice)

**Skills**
- `crypto-research` — when-to-invoke + tool-selection matrix
- `interpreting-market-data` — field-by-field legend + red flags

**Every response carries:**
- `reason_codes` audit trail (5-handler chain: `venue → symbol → cache → provider`)
- `staleness` + `cache_hit` — so you always know if data is fresh

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
- **Infrastructure (L2)** — `src/cryptozavr/infrastructure/`: CCXT adapter (KuCoin), CoinGecko HTTP client, Supabase gateway (asyncpg + supabase-py realtime), 4 decorators (Retry / RateLimit / InMemoryCache / Logging), 5-handler chain of responsibility.
- **Application (L4)** — `src/cryptozavr/application/services/`: `TickerService`, `OhlcvService`, `OrderBookService`, `TradesService` — thin orchestrators over chain + factory + gateway.
- **MCP (L5)** — `src/cryptozavr/mcp/`: FastMCP v3 server with lifespan, 4 tools, DTO layer.

14 GoF patterns applied: Template Method, Adapter, Bridge, Decorator (4 layered), Chain of Responsibility (5 handlers), State (venue health), Factory Method, Singleton via DI, Flyweight (SymbolRegistry), Facade (SupabaseGateway).

## Tests

    uv run pytest tests/unit tests/contract -m "not integration"   # 288 unit + 5 contract, ~2s
    uv run pytest tests/integration                                 # 14 live tests, ~40s (needs .env)

## Status

**v0.1.0** — plugin готов к marketplace distribution. Data layer (M2.1–M2.6) + Realtime (M2.7) complete. Next: analytical layer (signals/triggers/alerts) in M3.

## License

MIT — see [LICENSE](LICENSE).
