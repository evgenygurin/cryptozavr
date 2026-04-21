# cryptozavr — MVP Design

**Status:** Draft (awaiting user approval)
**Date:** 2026-04-21
**Scope:** Phase 0 + Phase 1 (MVP research-only market intelligence plugin)
**Author:** brainstorming session with Claude Code (Opus 4.7)

---

## Table of Contents

1. [Executive summary](#1-executive-summary)
2. [High-level architecture](#2-high-level-architecture)
3. [Domain model](#3-domain-model)
4. [Providers layer](#4-providers-layer)
5. [Application services](#5-application-services)
6. [Supabase layer](#6-supabase-layer)
7. [MCP server surface](#7-mcp-server-surface)
8. [Claude Code plugin structure](#8-claude-code-plugin-structure)
9. [Repository structure](#9-repository-structure)
10. [Testing strategy](#10-testing-strategy)
11. [Phased roadmap](#11-phased-roadmap)
12. [Hard red lines (project-wide)](#12-hard-red-lines-project-wide)
13. [GoF patterns map](#13-gof-patterns-map)
14. [Open questions / out of scope](#14-open-questions--out-of-scope)

---

## 1. Executive summary

### Goal

Создать Claude Code-плагин `cryptozavr` с встроенным FastMCP v3+ сервером, который даёт агенту дисциплинированную, риск-first, декларативную платформу для исследования крипторынка. MVP — **read-only market intelligence**: сканирование рынка, анализ символов, разбор ликвидности и режима. Никакой торговли в MVP.

### Philosophy

1. **Risk-first, not signal-first.** Даже в read-only MVP закладываем архитектуру, где risk engine (phase 3+) будет deterministic и стоять на критичном пути.
2. **Calm execution.** Никакой FOMO, revenge trading, overtrading. System prompt, tool design и mode model отражают хладнокровие.
3. **Declarative over ad-hoc.** Всё, что будет: стратегии, risk policies, execution policies — декларативные Pydantic-спеки, не императивный Python.
4. **Explainability and auditability.** Каждый ответ содержит `data`, `quality`, `reasoning`. Каждое решение записано.
5. **Safe agent design.** LLM не получает неограниченный доступ к critical actions. Capability split (read vs write), ModeGuard, PreToolUse-hooks (phase 5+), approval flow (phase 5+).

### Key decisions

| Decision | Value | Rationale |
|----------|-------|-----------|
| MVP scope | Foundation + market data providers (research-only) | Safe surface, полный цикл без капитала, фундамент для всех последующих фаз |
| Project form | Claude Code plugin с встроенным MCP-сервером | `plugin.json` + `.mcp.json` + skills + commands — единый пакет |
| Venues в MVP | CoinGecko (aggregator) + KuCoin (CEX через CCXT) | Один агрегатор + одна биржа = полный цикл discovery+details |
| Market data depth | Standard research: tickers + OHLCV + orderbook + trades | Тройка OHLCV/OB/trades — 90% research-запросов |
| Storage | Supabase (Postgres + Realtime + pg_cron + pgvector + Storage) | Managed стек; Realtime = Observer из коробки; pg_cron = scheduler |
| Supabase integration depth | Comprehensive (без Auth, без Edge Functions в MVP) | Realtime + pg_cron + Storage + pgvector-готовность — без overengineering с Auth |
| Architecture style | Hybrid — Layered Onion (A) + cache-aside through Supabase (element of C) | Чистые слои + event-driven hot data без тяжёлой event-sourced философии |
| Python tooling | uv + Python 3.12 + ruff + pytest + pydantic v2 | Современный быстрый стек |
| Postgres client | Hybrid: asyncpg (hot-path) + supabase-py (RPC/Storage) + realtime-py (Observer) | Правильный инструмент под каждую задачу, объединены Facade-ом |

### MVP deliverables

- 17 MCP tools (market intelligence, analysis, discovery, ops)
- 8 MCP resource URI-templates (venue/symbol/research/reference)
- 2 MCP prompts (market_overview, symbol_analysis)
- 3 Claude Code skills (market-scan, symbol-analysis, quality-check)
- 3 Claude Code slash-commands (/cryptozavr:scan, :analyze, :health)
- Full Supabase schema: 10 таблиц, RLS policies, pg_cron jobs
- Coverage 85%+ (95%+ на domain, 90%+ на providers)

### What MVP will NOT do

- Любая торговля (paper или live). Capability `SUBMIT_*` не существует в MVP.
- Стратегии в DSL-виде (phase 2).
- Risk engine (phase 3).
- Approval-flow (phase 5).
- Вторая биржа (phase 6).
- Multi-user / Auth.

---

## 2. High-level architecture

### Layered Onion

```mermaid
graph TB
    subgraph "L5 · MCP Facade (transport only)"
        T[Tools<br/>@mcp.tool]
        R[Resources<br/>@mcp.resource]
        P[Prompts<br/>@mcp.prompt]
        MW[Middleware<br/>logging/response-size]
    end

    subgraph "L4 · Application Services (use cases)"
        MDS[MarketDataService<br/>Facade]
        MA[MarketAnalyzer<br/>Strategy context]
        SR[SymbolResolver]
        SE[SessionExplainer]
        DS[DiscoveryService]
        OS[OpsService]
    end

    subgraph "L3 · Domain (pure)"
        DE[Entities]
        DI[Protocol interfaces]
        DV[Value objects]
    end

    subgraph "L2 · Infrastructure · Providers"
        CX[CCXTProvider<br/>→ KuCoin]
        CG[CoinGeckoProvider]
        DEC[Decorator chain:<br/>Logging → Caching →<br/>RateLimit → Retry]
        CHAIN[Chain of Responsibility<br/>pre-fetch validation]
        SG[SupabaseGateway<br/>Facade over<br/>asyncpg + supabase-py + realtime-py]
    end

    subgraph "L1 · Infrastructure · Platform"
        PG[(Supabase Postgres)]
        REAL[Supabase Realtime]
        CRON[pg_cron jobs]
        STOR[Supabase Storage]
    end

    T --> MDS
    R --> MDS
    P --> SE
    MDS --> MA
    MDS --> SR
    MDS --> CHAIN
    MA --> DI
    CHAIN --> DEC
    CHAIN --> SG
    DEC --> CX
    DEC --> CG
    CX -.impl.-> DI
    CG -.impl.-> DI
    SG --> PG
    SG --> REAL
    CRON --> PG
    SG --> STOR

    style DE fill:#2d4a2b,color:#fff
    style DI fill:#2d4a2b,color:#fff
    style DV fill:#2d4a2b,color:#fff
```

### Layer responsibilities

| Layer | Allowed | Forbidden |
|-------|---------|-----------|
| **L3 Domain** | Pydantic models, Protocol interfaces, value objects, enums, domain exceptions. Pure, in-RAM. | Import `httpx`/`ccxt`/`supabase`/`fastmcp`. Any I/O. |
| **L4 Application** | Use-case orchestration. Apply Strategy, Chain of Responsibility, Template Method, Command, Iterator. | Parse CCXT-dict, write SQL. These are L2 details. |
| **L5 MCP Facade** | `@mcp.tool` functions: input validation, service call, envelope formatting. Context injection for progress/logging. Middleware registration. | Business logic. Direct CCXT/Supabase calls. |
| **L2 Providers** | Adapters для внешних API, normalization to Domain, Decorator chain, domain exception raising. | Business decisions ("reject if spread > X"). Это L4. |
| **L1 Platform** | Supabase as managed infra. Migrations via Supabase CLI. | Python code. |

### Dependency Injection

Используем `punq` (или ручной composition root). Никаких глобалов. `Singleton` реализуется через `lifetime="singleton"` в контейнере.

```python
# infrastructure/composition_root.py (эскиз)
container = Container()
container.register(HttpClientRegistry, lifetime="singleton")
container.register(RateLimiterRegistry, lifetime="singleton")
container.register(SymbolRegistry, lifetime="singleton")
container.register(SupabaseGateway, lifetime="singleton")
container.register(MarketDataProvider, CCXTProvider, name="kucoin")
container.register(MarketDataProvider, CoinGeckoProvider, name="coingecko")
container.register(MarketDataService, lifetime="scoped")  # per-request
```

---

## 3. Domain model

### Layout

```text
src/cryptozavr/domain/
  value_objects.py       # Timeframe, Money, Instant, TimeRange, Percentage
  assets.py              # Asset, AssetCategory
  venues.py              # Venue, VenueCapability, VenueKind, VenueState
  symbols.py             # Symbol, SymbolRegistry (Flyweight)
  market_data.py         # Ticker, OHLCVCandle, OHLCVSeries, OrderBookSnapshot, TradeTick, MarketSnapshot
  quality.py             # DataQuality, Staleness, Confidence, Provenance
  interfaces.py          # MarketDataProvider, Repository, EventBus (Protocol)
  events.py              # VenueStateChanged и т.п. domain events
  exceptions.py          # иерархия DomainError
```

### Value objects (immutable, `frozen=True`)

- **`Timeframe`** — `StrEnum`: `M1`, `M5`, `M15`, `M30`, `H1`, `H4`, `D1`, `W1`. Methods: `to_milliseconds()`, `to_ccxt_string()`, `parse(str)`.
- **`Instant`** — UTC `datetime` wrapper. Rejects naive datetime. Methods: `from_ms(int)`, `from_iso(str)`, `to_ms()`, `isoformat()`, `now()`.
- **`TimeRange`** — `start: Instant, end: Instant`. Invariant `end > start`. Methods: `duration()`, `split(chunks)`, `contains(instant)`, `estimate_bars(timeframe)`.
- **`Money`** — `amount: Decimal, currency: str`. Never `float`. Validator: 3–10 uppercase chars for currency.
- **`Percentage`** — `Decimal` с методами `as_fraction()`, `as_bps()`.
- **`PriceSize`** — `(price: Decimal, size: Decimal)` tuple для уровней стакана.

### Entities

**`Asset`** (актив: BTC, ETH, USDT):
- `code: str` (normalized: "BTC")
- `name: str | None`, `category: AssetCategory | None` (`LAYER_1`, `DEFI`, `MEME`, `STABLECOIN`, ...)
- `market_cap_rank: int | None`
- `coingecko_id: str | None` — stable ID

**`Venue`** (биржа/источник: `kucoin`, `coingecko`):
- `id: VenueId` (enum)
- `kind: VenueKind` (`EXCHANGE_CEX`, `AGGREGATOR`, `EXCHANGE_DEX` future)
- `capabilities: frozenset[VenueCapability]` — (`SPOT_OHLCV`, `SPOT_ORDERBOOK`, `SPOT_TRADES`, `SPOT_TICKER`, `FUTURES_OHLCV`, `FUNDING_RATE`, `OPEN_INTEREST`, `MARKET_CAP_RANK`, `CATEGORY_DATA`)
- `state: VenueState` — runtime state, обновляется L2 (State pattern)

**`Symbol`** (инструмент: BTC/USDT на kucoin) — **Flyweight**:
- `venue: VenueId`, `base: str`, `quote: str`, `market_type: MarketType` (`SPOT`, `LINEAR_PERP`, `INVERSE_PERP`)
- `native_symbol: str` — формат venue ("BTC-USDT" на KuCoin)
- Получается только через `SymbolRegistry.get(...)` — один instance на процесс.

**`SymbolRegistry`** — Flyweight factory с `dict[tuple, Symbol]`. Thread-safe (asyncio lock). Заполняется при `load_markets()`.

**`Ticker`** — snapshot last/bid/ask/volume/change с `observed_at: Instant` и `quality: DataQuality`.

**`OHLCVCandle`** — `opened_at, open, high, low, close, volume, closed`. `closed: bool` — завершённость.

**`OHLCVSeries`** — `symbol, timeframe, candles: tuple, range, quality`. Methods: `last()`, `window(n)`, `slice(time_range)`, `merge(other)` — возвращают новые серии.

**`OrderBookSnapshot`** — `bids: tuple[PriceSize], asks: tuple[PriceSize], observed_at`. Methods: `best_bid()`, `best_ask()`, `spread()`, `spread_bps()`, `depth_within_bps(bps)`, `imbalance()`.

**`TradeTick`** — `symbol, price, size, side (BUY/SELL/UNKNOWN), timestamp`.

**`MarketSnapshot`** — композит: `ticker, orderbook?, recent_trades?, ohlcv: dict[Timeframe, OHLCVSeries]?`.

### Quality / Provenance

**`DataQuality`** (envelope для каждого ответа):
- `source: Provenance` — `(venue_id, endpoint)`
- `fetched_at: Instant`
- `staleness: Staleness` — `FRESH` / `RECENT` / `STALE` / `EXPIRED` (enum с порогами)
- `confidence: Confidence` — `HIGH` / `MEDIUM` / `LOW` / `UNKNOWN`
- `cache_hit: bool`

Все MCP tools возвращают `quality` вместе с данными — Claude видит, насколько можно доверять.

### Protocol interfaces

```python
# domain/interfaces.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class MarketDataProvider(Protocol):
    venue_id: VenueId
    async def load_markets(self) -> None: ...
    async def fetch_ticker(self, symbol: Symbol) -> Ticker: ...
    async def fetch_ohlcv(
        self, symbol: Symbol, timeframe: Timeframe,
        since: Instant | None = None, limit: int = 500,
    ) -> OHLCVSeries: ...
    async def fetch_order_book(self, symbol: Symbol, depth: int = 50) -> OrderBookSnapshot: ...
    async def fetch_trades(self, symbol: Symbol, since: Instant | None = None, limit: int = 100) -> tuple[TradeTick, ...]: ...
    async def close(self) -> None: ...

class Repository[T](Protocol):
    async def get(self, key) -> T | None: ...
    async def put(self, entity: T) -> None: ...
    async def list(self, **filters) -> list[T]: ...
```

**Bridge pattern:** `MarketDataProvider` — abstraction в Domain; `CCXTProvider`, `CoinGeckoProvider` — implementations в Infrastructure.

### Exception hierarchy

```text
DomainError
├── ValidationError
├── NotFoundError
│   ├── SymbolNotFoundError
│   └── VenueNotSupportedError
├── ProviderError
│   ├── ProviderUnavailableError
│   ├── RateLimitExceededError
│   └── AuthenticationError           # future
└── QualityError
    ├── StaleDataError
    └── IncompleteDataError
```

### Class relationships

```mermaid
classDiagram
    class Asset { +code +name +category +market_cap_rank +coingecko_id }
    class Venue { +id +kind +capabilities +state }
    class Symbol { +venue +base +quote +market_type +native_symbol }
    class SymbolRegistry { +get() }
    class Ticker { +symbol +last +bid +ask +volume_24h +observed_at +quality }
    class OHLCVSeries { +symbol +timeframe +candles +range +quality }
    class OrderBookSnapshot { +symbol +bids +asks +observed_at }
    class MarketSnapshot { +symbol +ticker +orderbook +ohlcv }
    class DataQuality { +source +fetched_at +staleness +confidence +cache_hit }

    Symbol --> Venue
    Symbol --> Asset
    SymbolRegistry ..> Symbol : flyweight factory
    Ticker --> Symbol
    OHLCVSeries --> Symbol
    OrderBookSnapshot --> Symbol
    MarketSnapshot --> Ticker
    MarketSnapshot --> OrderBookSnapshot
    MarketSnapshot --> OHLCVSeries
    Ticker --> DataQuality
    OHLCVSeries --> DataQuality
    OrderBookSnapshot --> DataQuality
```

### Patterns in this layer

- **Flyweight** — `SymbolRegistry`, `VenueRegistry`.
- **Value objects** — `Timeframe`, `Money`, `Instant`, `TimeRange`, `Percentage`.
- **Protocol-based Bridge** — `MarketDataProvider` + `Repository[T]`.

---

## 4. Providers layer

### Layout

```text
src/cryptozavr/infrastructure/providers/
  base.py                    # BaseProvider (Template Method)
  ccxt_provider.py           # CCXTProvider (concrete)
  coingecko_provider.py      # CoinGeckoProvider (concrete)
  factory.py                 # ProviderFactory (Factory Method)
  http.py                    # HttpClientRegistry
  rate_limiters.py           # RateLimiterRegistry
  adapters/
    ccxt_adapter.py          # raw CCXT dict → Domain
    coingecko_adapter.py     # raw JSON → Domain
  decorators/
    retry.py                 # RetryDecorator
    rate_limit.py            # RateLimitDecorator (token bucket)
    caching.py               # InMemoryCachingDecorator (L0)
    logging.py               # LoggingDecorator
  chain/
    handlers.py              # Chain of Responsibility
    assembly.py              # build_ohlcv_chain(), build_ticker_chain()
  state/
    venue_state.py           # State pattern: Healthy/Degraded/RateLimited/Down
    health_monitor.py        # периодический ping (phase 1.5)
```

### Template Method — `BaseProvider`

Фиксирует скелет fetch-операции, hooks — `_fetch_*_raw` и `_normalize_*`.

```python
# base.py (эскиз)
class BaseProvider(ABC, MarketDataProvider):
    def __init__(self, venue_id, state: VenueState):
        self.venue_id = venue_id
        self._state = state

    async def fetch_ticker(self, symbol) -> Ticker:
        return await self._execute(
            "fetch_ticker", symbol=symbol,
            fetch_raw=lambda: self._fetch_ticker_raw(symbol),
            normalize=lambda raw: self._normalize_ticker(raw, symbol),
        )

    async def _execute(self, operation, *, symbol, fetch_raw, normalize):
        self._state.require_operational()
        await self._ensure_markets_loaded()
        self._state.on_request_started(operation)
        try:
            raw = await fetch_raw()
        except Exception as exc:
            self._state.on_request_failed(operation, exc)
            raise self._translate_exception(exc)
        else:
            self._state.on_request_succeeded(operation)
            return normalize(raw)

    @abstractmethod
    async def _fetch_ticker_raw(self, symbol): ...
    @abstractmethod
    def _normalize_ticker(self, raw, symbol) -> Ticker: ...
    # ... и так далее для ohlcv/orderbook/trades
    @abstractmethod
    def _translate_exception(self, exc: Exception) -> Exception: ...
```

### Adapter

Pure functions `raw → Domain`, без I/O. Легко тестируются на fixtures.

```python
# adapters/ccxt_adapter.py (эскиз)
class CCXTAdapter:
    @staticmethod
    def ohlcv_to_series(raw: list[list], symbol, timeframe) -> OHLCVSeries:
        candles = tuple(
            OHLCVCandle(
                opened_at=Instant.from_ms(row[0]),
                open=Decimal(str(row[1])), high=Decimal(str(row[2])),
                low=Decimal(str(row[3])), close=Decimal(str(row[4])),
                volume=Decimal(str(row[5])), closed=True,
            )
            for row in raw
        )
        return OHLCVSeries(
            symbol=symbol, timeframe=timeframe, candles=candles,
            range=TimeRange(candles[0].opened_at, candles[-1].opened_at),
            quality=DataQuality(
                source=Provenance(venue_id=symbol.venue, endpoint="fetch_ohlcv"),
                fetched_at=Instant.now(),
                staleness=Staleness.FRESH, confidence=Confidence.HIGH,
                cache_hit=False,
            ),
        )
    # ticker_to_domain, orderbook_to_domain, trades_to_domain
```

### Concrete — `CCXTProvider`

```python
# ccxt_provider.py (эскиз)
import ccxt.async_support as ccxt

class CCXTProvider(BaseProvider):
    def __init__(self, venue_id, state, exchange_id="kucoin", **ccxt_opts):
        super().__init__(venue_id, state)
        self._exchange = getattr(ccxt, exchange_id)(
            {**ccxt_opts, "enableRateLimit": False},  # управляем сами
        )

    async def _ensure_markets_loaded(self):
        if not self._markets_loaded:
            await self._exchange.load_markets()
            self._markets_loaded = True

    async def _fetch_ohlcv_raw(self, symbol, timeframe, since, limit):
        return await self._exchange.fetch_ohlcv(
            symbol.native_symbol, timeframe.to_ccxt_string(),
            since=since.to_ms() if since else None, limit=limit,
        )

    def _normalize_ohlcv(self, raw, symbol, timeframe):
        return CCXTAdapter.ohlcv_to_series(raw, symbol, timeframe)

    def _translate_exception(self, exc):
        if isinstance(exc, ccxt.RateLimitExceeded):
            return RateLimitExceededError(str(exc))
        if isinstance(exc, ccxt.NetworkError):
            return ProviderUnavailableError(str(exc))
        return exc

    async def close(self):
        await self._exchange.close()
```

### Decorator chain

Композиция поведения без изменения BaseProvider.

**Order (outside → inside):**
```text
LoggingDecorator
  → InMemoryCachingDecorator (L0, TTL, перед rate-limiter — экономим лимит)
    → RateLimitDecorator (token bucket per-venue)
      → RetryDecorator (exponential backoff на ProviderUnavailableError)
        → CCXTProvider (base)
```

`RetryDecorator` **не** перехватывает `RateLimitExceededError` — для rate limits есть `RateLimitDecorator`, задерживающий запрос **до** отправки.

### Factory Method

```python
# factory.py
class ProviderFactory:
    def __init__(self, settings, rate_limiters, http_clients):
        self._settings = settings
        self._rate_limiters = rate_limiters
        self._http_clients = http_clients

    def create_kucoin(self) -> MarketDataProvider:
        state = VenueState(venue_id=VenueId.KUCOIN)
        provider: MarketDataProvider = CCXTProvider(
            venue_id=VenueId.KUCOIN, state=state, exchange_id="kucoin",
        )
        provider = RetryDecorator(provider, max_attempts=3)
        provider = RateLimitDecorator(provider, self._rate_limiters.get("kucoin"))
        provider = InMemoryCachingDecorator(provider, policy=self._settings.cache_policy("kucoin"))
        provider = LoggingDecorator(provider, logger=get_logger("provider.kucoin"))
        return provider

    def create_coingecko(self) -> MarketDataProvider: ...
```

### Chain of Responsibility — pre-fetch validation

```python
# chain/handlers.py (эскиз)
@dataclass
class FetchRequest:
    symbol: Symbol
    timeframe: Timeframe | None = None
    since: Instant | None = None
    limit: int = 500
    operation: str = "fetch_ticker"

@dataclass
class FetchContext:
    request: FetchRequest
    reason_codes: list[str]
    metadata: dict

class FetchHandler(ABC):
    _next: "FetchHandler | None" = None
    def set_next(self, h): self._next = h; return h
    @abstractmethod
    async def handle(self, ctx: FetchContext) -> FetchContext: ...
    async def _forward(self, ctx):
        return await self._next.handle(ctx) if self._next else ctx

class VenueHealthHandler(FetchHandler): ...       # проверка VenueState
class SymbolExistsHandler(FetchHandler): ...      # lookup в SymbolRegistry
class StalenessBypassHandler(FetchHandler): ...   # honour force_refresh
class SupabaseCacheHandler(FetchHandler): ...     # try gateway.load_*, short-circuit on fresh
class ProviderFetchHandler(FetchHandler): ...     # terminal: вызов Decorator chain

# assembly.py
def build_ohlcv_chain(gateway, states, registry, providers) -> FetchHandler:
    head = VenueHealthHandler(states)
    head.set_next(SymbolExistsHandler(registry)) \
        .set_next(StalenessBypassHandler()) \
        .set_next(SupabaseCacheHandler(gateway)) \
        .set_next(ProviderFetchHandler(providers))
    return head
```

`reason_codes` накапливаются естественно — готовый audit trail на уровне каждого запроса.

### State pattern — `VenueState`

```python
# state/venue_state.py (эскиз)
class VenueStateKind(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    RATE_LIMITED = "rate_limited"
    DOWN = "down"

class VenueStateHandler(ABC):
    @abstractmethod
    def require_operational(self, ctx): ...
    @abstractmethod
    def on_request_succeeded(self, ctx, op): ...
    @abstractmethod
    def on_request_failed(self, ctx, op, exc): ...

class HealthyState(VenueStateHandler):
    def on_request_failed(self, ctx, op, exc):
        ctx.error_count += 1
        if ctx.error_count >= 3:
            ctx.transition_to(DegradedState())

class DegradedState(VenueStateHandler):
    def on_request_succeeded(self, ctx, op):
        ctx.success_streak += 1
        if ctx.success_streak >= 5:
            ctx.transition_to(HealthyState())
    def on_request_failed(self, ctx, op, exc):
        if isinstance(exc, RateLimitExceededError):
            ctx.transition_to(RateLimitedState())

class RateLimitedState(VenueStateHandler):
    def require_operational(self, ctx):
        if ctx.now() < ctx.cooldown_until:
            raise ProviderUnavailableError("venue is rate-limited")

class DownState(VenueStateHandler):
    def require_operational(self, ctx):
        raise ProviderUnavailableError("venue is down")
```

Это honest circuit breaker без внешних библиотек, в стиле GoF State.

### Patterns map

| Pattern | Slot |
|---------|------|
| **Template Method** | `BaseProvider._execute` |
| **Adapter** | `CCXTAdapter`, `CoinGeckoAdapter` |
| **Bridge** | `MarketDataProvider` ↔ `CCXTProvider` / `CoinGeckoProvider` |
| **Decorator** | `LoggingDecorator → CachingDecorator → RateLimitDecorator → RetryDecorator → Base` |
| **Chain of Responsibility** | `VenueHealthHandler → SymbolExistsHandler → StalenessBypassHandler → SupabaseCacheHandler → ProviderFetchHandler` |
| **State** | `VenueState` + Healthy/Degraded/RateLimited/Down |
| **Factory Method** | `ProviderFactory` |
| **Singleton (DI)** | `HttpClientRegistry`, `RateLimiterRegistry`, `SymbolRegistry`, `SupabaseGateway` |

---

## 5. Application services

### Layout

```text
src/cryptozavr/application/
  services/
    market_data_service.py      # Facade — единственная точка входа для MCP tools
    market_analyzer.py          # Strategy context
    symbol_resolver.py          # string → Symbol
    session_explainer.py        # envelope formatter с quality+reasoning
    discovery_service.py        # CoinGecko trending/categories
    ops_service.py              # venue_health, refresh_symbol_map
  queries/
    market_query.py             # Command объект
    ohlcv_paginator.py          # Iterator
    query_log.py                # QueryLog Protocol
  strategies/                   # AnalysisStrategy family
    base.py                     # Protocol
    volatility.py
    regime.py
    liquidity.py
    momentum.py
  dtos/
    requests.py
    responses.py
  clock.py                      # Clock Protocol для тестируемости
```

### Facade — `MarketDataService`

Единственная точка входа для MCP tools. Видит только `MarketDataProvider`, `SupabaseGateway`, `FetchHandler` — не знает про CCXT или asyncpg.

```python
class MarketDataService:
    def __init__(
        self, ohlcv_chain, ticker_chain, orderbook_chain,
        symbol_resolver, gateway, query_log, clock,
    ): ...

    async def get_ohlcv(
        self, *, user_symbol, venue, timeframe,
        range=None, limit=500, force_refresh=False,
    ) -> OHLCVResult:
        symbol = await self._resolver.resolve(user_symbol, venue)
        query = MarketQuery.ohlcv(symbol, timeframe, range, limit, force_refresh)
        await self._query_log.record(query)

        ctx = FetchContext(request=query.to_fetch_request(), reason_codes=[], metadata={...})
        result_ctx = await self._ohlcv_chain.handle(ctx)
        series = result_ctx.metadata["result"]

        if not result_ctx.metadata.get("cache_hit"):
            await self._gateway.upsert_ohlcv(series)

        return OHLCVResult(series=series, reason_codes=tuple(result_ctx.reason_codes), query=query)

    async def get_market_snapshot(self, ...) -> SnapshotResult:
        """Композитный use-case: ticker + orderbook + ohlcv параллельно."""
        ...
```

### Strategy — `MarketAnalyzer` + `AnalysisStrategy`

```python
# strategies/base.py
class AnalysisStrategy(Protocol):
    name: str
    async def analyze(self, series: OHLCVSeries) -> AnalysisResult: ...

# strategies/volatility.py
class VolatilityAnalysisStrategy:
    name = "volatility"
    def __init__(self, atr_window=14): self._atr_window = atr_window
    async def analyze(self, series) -> AnalysisResult:
        atr = self._compute_atr(series, self._atr_window)
        realized_vol = self._compute_realized_vol(series)
        return AnalysisResult(strategy=self.name, findings={...}, confidence=Confidence.HIGH)

# services/market_analyzer.py
class MarketAnalyzer:
    def __init__(self, data: MarketDataService, strategies: dict[str, AnalysisStrategy]): ...
    async def analyze(self, *, user_symbol, venue, strategy_names, timeframe, lookback_bars) -> AnalysisReport:
        ohlcv = (await self._data.get_ohlcv(...)).series
        results = [await self._strategies[name].analyze(ohlcv) for name in strategy_names]
        return AnalysisReport(symbol=ohlcv.symbol, timeframe=timeframe, results=tuple(results))
```

Добавить `IchimokuAnalysisStrategy` в phase 2 = один файл, одно DI-регистрирование, нулевые изменения в `MarketAnalyzer`.

### SymbolResolver

Принимает любой user-input — `"BTC"`, `"btcusdt"`, `"BTC-USDT"`, `"Bitcoin"` — разрешает в `Symbol` в `SymbolRegistry`. Fuzzy через `pg_trgm` aliases + прямые lookups.

### Command — `MarketQuery`

Каждый market-data запрос — сериализуемый объект, который можно логировать, повторить, искать похожие.

```python
@dataclass(frozen=True)
class MarketQuery:
    id: UUID
    kind: MarketQueryKind                 # OHLCV/TICKER/ORDERBOOK/...
    symbol: Symbol | None
    timeframe: Timeframe | None
    range: TimeRange | None
    limit: int | None
    force_refresh: bool
    issued_at: Instant
    issued_by: str                         # 'mcp_tool:get_ohlcv'
    client_id: str | None
```

`QueryLog.record(query)` → INSERT в `cryptozavr.query_log` → audit trail.

### Iterator — `OHLCVPaginator`

Ленивая пагинация больших исторических окон (KuCoin limit ≤ 1500). Использует `async for` — MCP tool `fetch_ohlcv_history` стримит `ctx.report_progress` по мере накопления.

### SessionExplainer — envelope builder

Каждый tool-ответ оборачивается в envelope:

```json
{
  "data": {...},
  "quality": {
    "source": "kucoin:fetch_ohlcv",
    "fetched_at": "2026-04-21T10:05:00Z",
    "staleness": "fresh",
    "confidence": "high",
    "cache_hit": false
  },
  "reasoning": {
    "query_id": "7f9b...",
    "chain_decisions": ["venue:healthy", "cache:miss", "provider:called"],
    "notes": []
  }
}
```

### Patterns map

| Pattern | Slot |
|---------|------|
| **Facade** | `MarketDataService`, `MarketAnalyzer` |
| **Strategy** | `AnalysisStrategy` family + `MarketAnalyzer` |
| **Command** | `MarketQuery` |
| **Iterator** | `OHLCVPaginator` |
| **Chain of Responsibility (usage)** | `MarketDataService` orchestrates chain from L2 |
| **(implicit) Mediator** | `MarketDataService` coordinates Resolver+Chain+Gateway+QueryLog |

**Нет** в этом слое намеренно: Builder (появится в phase 2 для StrategySpec), Visitor (в phase 2 для backtest analytics), Memento (в phase 4 для decision replay).

---

## 6. Supabase layer

### Strategy

- Отдельная схема `cryptozavr` (не `public`).
- Два клиента под капотом `SupabaseGateway`: **asyncpg** (hot-path: bulk upsert OHLCV, range reads), **supabase-py async** (RPC, Storage, admin), **realtime-py** (`AsyncRealtimeClient` для Observer).
- Миграции — Supabase CLI, SQL в `supabase/migrations/`.

### Migrations (MVP)

```text
supabase/migrations/
  00000000000000_extensions.sql           # vector, pg_cron, pg_net, pg_trgm
  00000000000010_reference.sql            # venues, assets, symbols, symbol_aliases
  00000000000020_market_data.sql          # tickers_live, ohlcv_candles, orderbook_snapshots, trades
  00000000000030_audit.sql                # query_log, provider_events
  00000000000040_rls.sql                  # RLS policies (service_role full, anon none)
  00000000000050_cron.sql                 # pg_cron jobs
```

### Key tables (excerpt)

**`cryptozavr.ohlcv_candles`** (миллионы строк):
```sql
create table cryptozavr.ohlcv_candles (
  symbol_id     bigint not null references cryptozavr.symbols(id) on delete cascade,
  timeframe     cryptozavr.timeframe not null,
  opened_at     timestamptz not null,
  open          numeric(38, 18) not null,
  high          numeric(38, 18) not null,
  low           numeric(38, 18) not null,
  close         numeric(38, 18) not null,
  volume        numeric(38, 18) not null,
  closed        boolean not null default true,
  fetched_at    timestamptz not null default now(),
  primary key (symbol_id, timeframe, opened_at)
);
create index ohlcv_by_symbol_tf_opened_desc
  on cryptozavr.ohlcv_candles (symbol_id, timeframe, opened_at desc);
```

**`cryptozavr.tickers_live`** — hot cache, one row per symbol:
```sql
create table cryptozavr.tickers_live (
  symbol_id       bigint primary key references cryptozavr.symbols(id) on delete cascade,
  last            numeric(38, 18) not null,
  bid             numeric(38, 18),
  ask             numeric(38, 18),
  volume_24h      numeric(38, 18),
  change_24h_pct  numeric(10, 6),
  high_24h        numeric(38, 18),
  low_24h         numeric(38, 18),
  observed_at     timestamptz not null,
  fetched_at      timestamptz not null default now(),
  source_endpoint text not null default 'fetch_ticker'
);
```

**`cryptozavr.query_log`** (audit + future pgvector):
```sql
create table cryptozavr.query_log (
  id             uuid primary key default gen_random_uuid(),
  kind           cryptozavr.query_kind not null,
  symbol_id      bigint references cryptozavr.symbols(id),
  timeframe      cryptozavr.timeframe,
  range_start    timestamptz,
  range_end      timestamptz,
  limit_n        int,
  force_refresh  boolean not null default false,
  reason_codes   text[] not null default '{}',
  quality        jsonb,
  issued_by      text not null,
  client_id      text,
  issued_at      timestamptz not null default now(),
  query_embedding extensions.halfvec(1536)       -- phase 2+
);
```

### RLS

В MVP service_role полный доступ, anon — ничего. Пример policy:

```sql
alter table cryptozavr.ohlcv_candles enable row level security;

create policy service_role_full_access on cryptozavr.ohlcv_candles
  for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');
```

### pg_cron jobs

```sql
-- Обновление symbols с KuCoin каждые 6 часов
select cron.schedule('refresh-kucoin-symbols', '0 */6 * * *',
  $$ select cryptozavr.refresh_symbols_job('kucoin') $$);

-- Чистим stale tickers каждые 15 минут
select cron.schedule('prune-stale-tickers', '*/15 * * * *',
  $$ delete from cryptozavr.tickers_live where observed_at < now() - interval '5 minutes' $$);

-- Retention query_log — 30 дней
select cron.schedule('prune-query-log', '0 3 * * *',
  $$ delete from cryptozavr.query_log where issued_at < now() - interval '30 days' $$);
```

Функция `cryptozavr.refresh_symbols_job('kucoin')` не ходит в CCXT из Postgres, а пишет marker в `cryptozavr.maintenance_queue`. Python worker (`SymbolMapRefresher` как `@mcp.tool(task=True)` или отдельный background-process) подхватывает.

### SupabaseGateway — Facade

```python
class SupabaseGateway:
    def __init__(self, pg_pool, supabase, realtime, symbol_registry): ...

    # Hot-path через asyncpg
    async def load_ohlcv(self, symbol, timeframe, since, limit) -> OHLCVSeries | None: ...
    async def upsert_ohlcv(self, series: OHLCVSeries) -> None: ...
    async def upsert_ticker(self, ticker: Ticker) -> None: ...

    # Audit
    async def record_query(self, query: MarketQuery) -> None: ...
    async def record_provider_event(self, event) -> None: ...

    # Realtime (Observer)
    async def subscribe_tickers(self, venue_id, callback) -> SubscriptionHandle: ...

    # Storage (phase 2+ в основном)
    async def upload_report(self, bucket, key, data, content_type) -> str: ...

    # RPC (phase 2+ для pgvector)
    async def match_regimes(self, embedding, threshold, limit) -> list[dict]: ...
```

### pgvector

Расширение включено. `query_embedding halfvec(1536)` в `query_log` — колонка nullable, в MVP не заполняется. HNSW index создаётся миграцией в phase 2 (не на пустой таблице).

### Patterns map

| Pattern | Slot |
|---------|------|
| **Facade** | `SupabaseGateway` над asyncpg + supabase-py + realtime-py |
| **Adapter** | `_rows_to_ohlcv_series`, `_payload_to_ticker` |
| **Observer** | `subscribe_tickers` через `postgres_changes` |
| **Singleton (DI)** | `SupabaseGateway`, `asyncpg.Pool` |
| **Cache-Aside (architectural)** | Gateway.load_ohlcv + MarketDataService fallback to provider |

---

## 7. MCP server surface

### Layout

```text
src/cryptozavr/mcp/
  server.py                     # build_server() + main()
  settings.py                   # Pydantic Settings из env
  tools/
    market.py                   # 10 market intelligence tools
    analysis.py                 # 2 analysis tools
    discovery.py                # 3 discovery tools
    ops.py                      # 2 ops tools
  resources/
    venue.py, symbol.py, research.py, reference.py
  prompts/
    research.py
  schemas/
    requests.py, responses.py, enums.py
  middleware/
    logging.py, quality_envelope.py
  modes/
    guard.py                    # ModeGuard
```

### Tools (17)

**Market intelligence (10):** `list_venues`, `list_supported_timeframes`, `resolve_symbol`, `get_ticker`, `get_tickers_batch`, `get_ohlcv`, `fetch_ohlcv_history` (task=True), `get_orderbook`, `get_recent_trades`, `get_market_snapshot`.

**Analysis (2):** `analyze_symbol`, `compare_symbols`.

**Discovery (3):** `list_trending`, `list_categories`, `list_assets_by_category`.

**Ops (2):** `venue_health`, `refresh_symbol_map` (task=True).

### Canonical tool template

```python
@market_tools.tool(
    name="get_ohlcv",
    description="Получить OHLCV-свечи для символа. Возвращает envelope с data/quality/reasoning.",
    tags={"market-data", "ohlcv", "read-only", "mvp"},
    timeout=30.0,
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
)
async def get_ohlcv(
    user_symbol: Annotated[str, Field(description="...")],
    venue: Annotated[VenueId, Field(description="...")],
    timeframe: Annotated[Timeframe, Field(description="...")] = Timeframe.H1,
    limit: Annotated[int, Field(ge=1, le=1500)] = 500,
    since_iso: Annotated[str | None, Field(description="ISO-8601 start")] = None,
    force_refresh: Annotated[bool, Field(description="Обойти кеш")] = False,
    ctx: Context,
) -> OhlcvResponse:
    guard.ensure(Capability.READ_MARKET_DATA)
    await ctx.info(f"Resolving {user_symbol} on {venue}")
    since = Instant.from_iso(since_iso) if since_iso else None
    result = await service.get_ohlcv(
        user_symbol=user_symbol, venue=venue, timeframe=timeframe,
        range=TimeRange(since, Instant.now()) if since else None,
        limit=limit, force_refresh=force_refresh,
    )
    return explainer.build_response_envelope(
        result=OhlcvResponse.from_series(result.series),
        reason_codes=result.reason_codes,
        query=result.query, quality=result.series.quality,
    )
```

**Shape:** `guard → resolve → delegate → envelope`. Body не содержит доменной логики.

### Resources (8 URI-шаблонов)

```text
venue://{venue_id}/manifest          # capabilities, limits, last sync
venue://{venue_id}/state             # VenueState + 24h history
symbol://{venue_id}/{base}_{quote}/manifest
symbol://{venue_id}/{code}/meta      # CoinGecko metadata
research://queries/recent?limit=50&client_id=<id>
research://queries/{query_id}
reference://timeframes
reference://market-categories
reference://venues
```

**Важно** (из v3-notes): resources возвращают `str` / `bytes` / `ResourceResult`. Dict/list raises TypeError. Используем `model_dump_json()`.

### Prompts (2)

- `market_overview` — system prompt для широкого скана (focus_venue, focus_quote, horizon).
- `symbol_analysis` — deep-dive procedure для одного символа.

### Providers composition

```python
def build_server(settings) -> FastMCP:
    container = build_container(settings)
    service = container.resolve(MarketDataService)
    analyzer = container.resolve(MarketAnalyzer)
    explainer = container.resolve(SessionExplainer)
    guard = container.resolve(ModeGuard)

    market_provider = register_market_tools(service, explainer, guard)
    analysis_provider = register_analysis_tools(analyzer, explainer, guard)
    discovery_provider = register_discovery_tools(service, explainer, guard)
    ops_provider = register_ops_tools(container.resolve(OpsService), explainer, guard)
    resource_providers = [venue_resources, symbol_resources, research_resources, reference_resources]
    skills_provider = SkillsDirectoryProvider(roots=settings.skills_roots)

    mcp = FastMCP(
        name="cryptozavr-research", version="0.1.0",
        providers=[
            market_provider, analysis_provider, discovery_provider, ops_provider,
            *resource_providers, research_prompts, skills_provider,
        ],
    )
    mcp.add_middleware(LoggingMiddleware(include_payloads=False))
    mcp.add_middleware(ResponseLimitingMiddleware(max_size=500_000))
    return mcp
```

### ModeGuard

```python
class Capability(StrEnum):
    READ_MARKET_DATA = "read_market_data"
    READ_PORTFOLIO = "read_portfolio"                        # phase 2+
    WRITE_PORTFOLIO = "write_portfolio"                      # phase 3+
    SUBMIT_PAPER_ORDERS = "submit_paper_orders"              # phase 4+
    SUBMIT_LIVE_ORDERS_REQUEST = "submit_live_orders_request" # phase 5+
    SUBMIT_LIVE_ORDERS_EXECUTE = "submit_live_orders_execute" # phase 5+ + approval
    ADMIN_RUNTIME = "admin_runtime"

MODE_CAPABILITIES[Mode.RESEARCH_ONLY] = frozenset({
    Capability.READ_MARKET_DATA,
    Capability.ADMIN_RUNTIME,
})
```

Любой tool вызывает `guard.ensure(Capability.X)` первым делом. Несовпадение → `CapabilityDeniedError`.

### Visibility

Все MVP tools tagged `"mvp"` + `"capability:<name>"`. Phase-2+ tools получат tag `"phase-2"` и будут скрыты в MVP через `mcp.disable(tags={"phase-2"})`.

### Patterns map

| Pattern | Slot |
|---------|------|
| **Composite (FastMCP)** | `AggregateProvider` внутри FastMCP — объединяет все LocalProviders |
| **Decorator / CoR (FastMCP)** | Middleware chain |
| **Facade (service calls)** | Tool bodies → `service.method()` |
| **Command (FastMCP Task)** | `@mcp.tool(task=True)` — Task object для cancel/await |
| **Visibility (VisibilityFilter)** | Tag-based hiding |

---

## 8. Claude Code plugin structure

### `plugin.json`

```json
{
  "name": "cryptozavr",
  "version": "0.1.0",
  "description": "Risk-first crypto market research plugin for Claude Code. Read-only MVP.",
  "author": { "name": "cryptozavr", "email": "e.a.gurin@outlook.com" },
  "license": "MIT",
  "keywords": ["crypto", "market-data", "research", "fastmcp", "supabase"],
  "mcpServers": ["cryptozavr-research"],
  "skills": "skills/",
  "commands": "commands/",
  "hooks": "hooks/hooks.json"
}
```

### `.mcp.json`

```json
{
  "mcpServers": {
    "cryptozavr-research": {
      "command": "sh",
      "args": [
        "-c",
        ". ${CLAUDE_PLUGIN_ROOT}/.env && uv run --directory ${CLAUDE_PLUGIN_ROOT} python -m cryptozavr.mcp.server"
      ],
      "env": { "PYTHONUNBUFFERED": "1" }
    }
  }
}
```

`sh -c . .env && uv run ...` — чтобы expand `${SUPABASE_URL}` etc. из локального `.env`.

### `fastmcp.json`

```json
{
  "$schema": "https://gofastmcp.com/public/schemas/fastmcp.json/v1.json",
  "source": { "path": "src/cryptozavr/mcp/server.py", "entrypoint": "mcp" },
  "environment": {
    "python": ">=3.12,<3.14",
    "dependencies": [
      "fastmcp>=3.2.4", "fastmcp[tasks,apps]",
      "pydantic>=2.9", "pydantic-settings>=2.5",
      "httpx>=0.27", "ccxt>=4.4",
      "asyncpg>=0.29", "supabase>=2.8", "realtime>=2.0",
      "structlog>=24", "punq>=0.7"
    ]
  }
}
```

### Skills (3 в MVP)

```text
skills/
  market-scan/SKILL.md
  symbol-analysis/
    SKILL.md
    references/tf-selection.md
    references/quality-flags.md
  quality-check/SKILL.md
```

Каждая `SKILL.md` — frontmatter + процедура (When to use / Workflow / Constraints / Output format / What NOT to do).

### Commands (3)

```text
commands/
  scan.md             # /cryptozavr:scan [focus]
  analyze.md          # /cryptozavr:analyze <symbol>
  health.md           # /cryptozavr:health
```

### Hooks

**MVP: пусто.** В phase 1.5+ добавим `SessionStart` hook для инъекции venue_health. В phase 5+ — `PreToolUse` для блокировки execution tools вне нужного Mode.

### Installation

**Dev-link (рекомендованный MVP workflow):**
```bash
cd /Users/laptop/dev/cryptozavr
uv sync
cp .env.example .env && vim .env
supabase start
supabase db push
/plugin link ./          # в Claude Code
```

---

## 9. Repository structure

```text
cryptozavr/
├── plugin.json                      # Claude Code plugin manifest
├── .mcp.json                        # MCP-сервер регистрация
├── fastmcp.json                     # FastMCP runtime config
├── pyproject.toml                   # uv project metadata
├── uv.lock
├── README.md
├── CHANGELOG.md
├── LICENSE
├── .env.example
├── .gitignore
├── .editorconfig
├── .python-version                  # 3.12
│
├── .claude/
│   ├── cryptozavr.local.md          # plugin-settings local
│   └── settings.local.json
│
├── config/
│   ├── default.toml                 # mode=research_only, TTLs, rate limits
│   ├── local.toml                   # overrides
│   └── schema.py                    # Pydantic Settings
│
├── docs/
│   ├── README.md
│   ├── architecture/
│   │   ├── overview.md
│   │   ├── patterns.md
│   │   └── modes.md
│   ├── providers/
│   │   ├── kucoin.md
│   │   └── coingecko.md
│   ├── skills-and-playbooks.md
│   ├── superpowers/specs/
│   │   └── 2026-04-21-cryptozavr-mvp-design.md  # этот документ
│   └── runbooks/
│
├── skills/
│   ├── market-scan/SKILL.md
│   ├── symbol-analysis/
│   │   ├── SKILL.md
│   │   └── references/
│   └── quality-check/SKILL.md
│
├── commands/
│   ├── scan.md
│   ├── analyze.md
│   └── health.md
│
├── hooks/
│   └── .gitkeep
│
├── supabase/
│   ├── config.toml
│   ├── migrations/
│   │   ├── 00000000000000_extensions.sql
│   │   ├── 00000000000010_reference.sql
│   │   ├── 00000000000020_market_data.sql
│   │   ├── 00000000000030_audit.sql
│   │   ├── 00000000000040_rls.sql
│   │   └── 00000000000050_cron.sql
│   ├── functions/                   # phase 2+
│   ├── seed.sql
│   └── tests/
│
├── src/cryptozavr/
│   ├── __init__.py
│   ├── domain/                      # L3
│   ├── application/                 # L4
│   ├── infrastructure/              # L1+L2
│   │   ├── composition_root.py
│   │   ├── providers/
│   │   ├── supabase/
│   │   ├── repositories/
│   │   ├── observability/
│   │   └── maintenance/
│   └── mcp/                         # L5
│
├── tests/
│   ├── conftest.py
│   ├── unit/                        # ~200 тестов
│   ├── contract/                    # ~40
│   ├── integration/                 # ~20 (supabase start)
│   ├── mcp/                         # ~30 (direct server calls)
│   ├── e2e/                         # 1-3 smoke
│   └── fixtures/
│       ├── kucoin/                  # saved raw responses
│       └── coingecko/
│
├── scripts/
│   ├── bootstrap-supabase.sh
│   ├── refresh-fixtures.py
│   └── health-probe.py
│
└── .github/workflows/
    ├── ci.yml
    └── plugin-validate.yml
```

---

## 10. Testing strategy

### Pyramid

```text
       e2e  (1-3 smoke roundtrip через STDIO)
    ─────
    mcp tests  (~30 direct server calls)
  ─────────
  integration  (~20 Supabase Gateway, pg_cron, Realtime)
────────────
contract       (~40 Adapters vs saved raw fixtures)
──────────────
unit           (~200+ Domain, Application, pure Infrastructure)
```

### Tooling

`pytest 8.3+`, `pytest-asyncio` (mode=auto), `pytest-cov`, `pytest-xdist`, `respx`, `freezegun`/`time-machine`, `hypothesis`, `polyfactory`, `dirty-equals`.

### Coverage targets

| Layer | Target |
|-------|--------|
| Domain | 95%+ |
| Application | 85%+ |
| Providers (adapters/decorators/chain/state) | 90%+ |
| Supabase | 70%+ (integration-only) |
| MCP layer | 80%+ |
| **Overall** | **85%+** (enforced in CI) |

### Unit tests

Ноль I/O, быстрые (сумма <15s), детерминированные (Clock через DI).

Примеры:
- `SymbolRegistry` возвращает один instance на concurrent-вызовах.
- `OHLCVSeries.slice(range)` корректен через Hypothesis.
- `RetryDecorator` делает 3 попытки с exponential backoff.
- Chain: невалидный symbol → `SymbolNotFoundError` на SymbolExistsHandler.
- State: Healthy → Degraded после 3 errors → Healthy после 5 successes.

### Contract tests

Сохранённые raw API responses в `tests/fixtures/`. `respx` перехватывает `httpx` и возвращает fixture. Обновление — вручную через `scripts/refresh-fixtures.py` (раз в релиз, не CI).

### Integration tests

Требуют `supabase start` локально. В CI — job с docker.

Покрытие:
- OHLCV upsert+load roundtrip.
- Conflict resolution (upsert overrides).
- pg_cron `prune-stale-tickers` удаляет.
- `subscribe_tickers` ловит INSERT ≤ 2s.
- RLS: service_role читает, anon — нет.
- Миграции применяются чисто.

### MCP tests

**Canonical v3 pattern:** direct server calls через `mcp.call_tool(...)`, не Client wrapper.

```python
async def test_get_ohlcv_returns_envelope(mcp_server, in_memory_services):
    result = await mcp_server.call_tool("get_ohlcv", {
        "user_symbol": "BTC/USDT", "venue": "kucoin",
        "timeframe": "1h", "limit": 100,
    })
    data = result.structured_content
    assert "data" in data and "quality" in data and "reasoning" in data
    assert data["quality"]["source"].startswith("kucoin:")
```

### E2E tests

`@pytest.mark.e2e`, запуск только на `main` branch. Один smoke: STDIO roundtrip `list_tools` + `call_tool("get_ticker", ...)` с fake provider.

### CI pipeline

Три job'а: `lint` (ruff + mypy), `unit-contract` (быстрые тесты), `integration` (supabase start + mcp + integration). `plugin-validate` — проверка schemas `plugin.json`/`.mcp.json`/skills frontmatter.

---

## 11. Phased roadmap

### Phase 0 — Bootstrap (1-2 дня)

- `pyproject.toml`, `uv`, `ruff`, `pytest`, pre-commit.
- `supabase init`, локальный `supabase start`.
- Empty `plugin.json`, `.mcp.json`, `fastmcp.json` + echo-tool.
- CI: lint + smoke.

**Acceptance:** `/plugin link ./` в Claude Code показывает cryptozavr connected.

### Phase 1 — MVP (3-4 недели)

**Scope:** полная реализация всего, что описано в разделах 3–10.

**Acceptance:**
- Все 17 tools отвечают envelope-ом.
- `/cryptozavr:scan trending` проходит end-to-end.
- `/cryptozavr:analyze BTC/USDT` возвращает carded analysis.
- `fetch_ohlcv_history` стримит progress через task.
- pg_cron jobs работают.
- CI green (unit + contract + mcp + integration).
- Coverage ≥ 85%.

**Red lines:** никаких write-capabilities, никаких API keys бирж, никаких strategies/risk/execution.

### Phase 1.5 — Realtime + Observability (1-1.5 недели)

- Supabase Realtime: подписка на `tickers_live`, invalidate L0 cache.
- `TickerSyncWorker` background task.
- `MetricsDecorator` (Prometheus).
- `HealthMonitor` — периодический ping.
- `SessionStart` hook — инжект venue_health summary.
- 2 новые skills: `venue-debug`, `post-session-reflection`.

**Red lines:** те же, что Phase 1.

### Phase 2 — Declarative strategy engine + backtest (4-6 недель)

- StrategySpec DSL (Pydantic).
- `StrategySpecBuilder` (Builder pattern).
- BacktestEngine с slippage/fee simulation.
- Visitor pattern для post-backtest analytics.
- 8 новых MCP tools (validate/backtest/compare/stress_test/explain/list/save/diff).
- pgvector активируется (strategy_specs embedding).
- Skill `strategy-review`.

**Red lines:** никакого live и paper execution.

### Phase 3 — Risk engine + declarative policies (3-4 недели)

- RiskPolicy / ExecutionPolicy / PortfolioPolicy DSL.
- Deterministic RiskEngine (Chain of Responsibility: `RiskPolicyHandler → ExposureHandler → LiquidityHandler → CooldownHandler → KillSwitchHandler`).
- 6 новых tools.
- `EVALUATE_RISK` capability (read-only).

**Red lines:** LLM не переопределяет RiskEngine. Ни одного live ордера.

### Phase 4 — Paper trading + execution planner (3-4 недели)

- PaperPortfolio (in-memory + Supabase).
- ExecutionPlanner (TradeIntent → ExecutionPlan).
- PaperExecutionEngine.
- 7 новых tools.
- Approval provider (по умолчанию включён даже в paper).
- Mode `PAPER_TRADING` активирован.

**Red lines:** нет live execution. Нет API keys бирж.

### Phase 5 — Approval-gated live execution (4-6 недель)

- API key management (Supabase Vault).
- LiveExecutionEngine (Strategy: Live vs Paper — один protocol).
- Approval flow обязателен. TTL 5 минут.
- KillSwitch + PreToolUse hook.
- Full audit trail.
- Mode `APPROVAL_GATED_LIVE` активирован (opt-in).
- Hard cap $1000 notional первый месяц.

**Red lines:**
- Нет auto-live без approval.
- Нет withdrawals/transfers.
- Нет leverage > 1x (spot only).
- Подъём cap — через новую миграцию, не env.

### Phase 6+ — Future

- Policy-constrained auto-live (отдельный дизайн).
- Вторая CEX (Bybit/OKX).
- Perpetual futures.
- DEX-интеграция.
- News/sentiment (с prompt-injection защитой).
- CodeMode transform.
- Multi-user + Auth.
- Edge Functions для webhooks.
- Remote HTTP deployment.
- CoinMarketCap параллельно с CoinGecko.

Каждая фаза — отдельный brainstorming → spec → plan → implementation цикл.

---

## 12. Hard red lines (project-wide)

Эти правила — не рекомендации, а **инварианты**. Нарушение = архитектурный фейл.

1. **No LLM autonomy for capital-impacting actions.** LLM предлагает, человек подтверждает, deterministic code исполняет. Нет исключений.
2. **RiskEngine is deterministic Python.** Нет `ctx.sample(...)` внутри risk logic. Нет LLM-reasoning в pre-trade chain.
3. **Никаких mock-данных в production-пути.** Либо реальный provider + adapter, либо фича не ship'ится. Нет "пока замокаем".
4. **Audit trail immutable.** `query_log`, `risk_decisions`, `approvals`, `live_orders` — INSERT only на уровне RLS. UPDATE/DELETE запрещены даже service_role. Корректировки — через новые записи со ссылкой на исходную.
5. **Credentials never in code/git.** `.env.example` — только названия. `.env` — `.gitignored`. Phase 5+: Supabase Vault / macOS Keychain.
6. **Error → reason_code, not silent fallback.** Нельзя вернуть `[]` и надеяться, что пользователь не заметит. Либо явный error, либо envelope с `quality.staleness=EXPIRED` и `notes`.
7. **State transitions are traceable.** Каждый `VenueState` transition → `provider_events` insert. Каждое policy-решение → `risk_decisions` insert. Без explicit audit событие не происходит.
8. **No destructive CLI scripts without guard.** Любой script, удаляющий/пересоздающий данные, требует явного `--confirm-data-loss` и блокируется в CI для prod-like окружений.

---

## 13. GoF patterns map

Применённые паттерны (22 из предоставленных GoF + классика) с раскладкой по слоям.

### Applied in MVP

| # | Pattern | Layer | Concrete slot |
|---|---------|-------|----------------|
| 1 | **Adapter** | L2 | `CCXTAdapter`, `CoinGeckoAdapter`, SupabaseGateway row-mappers |
| 2 | **Bridge** | L3 ↔ L2 | `MarketDataProvider` (Domain) ↔ `CCXTProvider`/`CoinGeckoProvider` (Infra) |
| 3 | **Chain of Responsibility** | L2 + FastMCP middleware | pre-fetch validation chain; FastMCP middleware pipeline |
| 4 | **Command** | L4 | `MarketQuery` → QueryLog persistence |
| 5 | **Decorator** | L2 | `Logging → Caching → RateLimit → Retry → Base` provider chain |
| 6 | **Facade** | L4, L1 | `MarketDataService`, `MarketAnalyzer`, `SupabaseGateway` |
| 7 | **Factory Method** | L2 | `ProviderFactory.create_kucoin()`, `create_coingecko()` |
| 8 | **Flyweight** | L3 | `SymbolRegistry`, `VenueRegistry` |
| 9 | **Iterator** | L4 | `OHLCVPaginator` (async iterator над большими историческими окнами) |
| 10 | **Observer** | L1 ↔ L4 | Supabase Realtime `postgres_changes` → MCP session cache (phase 1.5) |
| 11 | **Singleton (via DI)** | L1, L2 | `HttpClientRegistry`, `RateLimiterRegistry`, `SymbolRegistry`, `SupabaseGateway`, `asyncpg.Pool` |
| 12 | **State** | L2 | `VenueState` + Healthy/Degraded/RateLimited/Down handlers |
| 13 | **Strategy** | L4 | `AnalysisStrategy` family + `MarketAnalyzer` context |
| 14 | **Template Method** | L2 | `BaseProvider._execute` |

### Deferred (future phases)

| # | Pattern | When |
|---|---------|------|
| 15 | **Abstract Factory** | Phase 6 (2-й venue): семейство `Connector + Normalizer + RateLimiter + AuthConfig` |
| 16 | **Builder** | Phase 2: `StrategySpecBuilder` для пошаговой сборки стратегий |
| 17 | **Composite** | Phase 2+: `AggregatedMarketData` composite provider |
| 18 | **Mediator** | Phase 3+: `TradingMediator` координирует Strategy + Risk + Execution |
| 19 | **Memento** | Phase 4: decision replay, snapshot snapshots |
| 20 | **Prototype** | Phase 2: strategy cloning (через `model_copy(update={...})`) |
| 21 | **Proxy** | Неявно присутствует через Decorator (cache proxy). Явно — не нужен. |
| 22 | **Visitor** | Phase 2: post-backtest analytics (`SharpeVisitor`, `MaxDrawdownVisitor`) |

---

## 14. Open questions / out of scope

### Out of scope for MVP (explicitly)

- Multi-user / Auth (phase 6+).
- Remote HTTP deployment (phase 6+).
- Edge Functions для webhooks (phase 4+).
- CodeMode transform (phase 6+).
- Второй venue (phase 6).
- Derivatives (perpetual futures) — phase 6+ с отдельным дизайном.
- News/sentiment providers (phase 6+).

### Open questions (для будущих фаз, не блокеров MVP)

1. **Embedding provider для pgvector.** Когда в phase 2 будем заполнять `query_embedding` / `strategy_embedding` — какой модели использовать? OpenAI `text-embedding-3-small` (1536 dim) подходит под halfvec(1536), но требует API key. Альтернативы: локальный `bge-small-en` через ONNX, Supabase-hosted `gte-small` (384 dim).
2. **Testcontainers vs supabase start в CI.** Supabase CLI в CI — docker-in-docker, возможны flaky тесты. Testcontainers[postgres] быстрее, но не даёт Realtime/Storage. Решим при первых CI runs.
3. **pg_cron + CCXT gap.** `refresh_symbols_job` пишет marker в `maintenance_queue` → Python worker подхватывает. Альтернатива: `pg_net.http_post` → Edge Function → node-скрипт с CCXT. Marker-подход проще, но требует постоянно запущенного Python worker. В MVP стартуем через `@mcp.tool(task=True)` — ручной refresh. В phase 1.5 — автоматизируем.
4. **Rate limiter granularity.** Per-venue или per-(venue, endpoint)? KuCoin имеет разные лимиты для public vs authed. В MVP public-only — per-venue достаточно. В phase 5 понадобится per-endpoint.
5. **Clock Protocol usage.** Везде ли использовать `Clock.now()` через DI, или `Instant.now()` прямой вызов? Решение: domain value objects могут делать `Instant.now()` (pure, мгновенно). Сервисы — через `Clock` для тестируемости с freeze.

### Known risks

| Risk | Mitigation |
|------|------------|
| CoinGecko free tier rate limit (30 req/min) | Aggressive caching в Supabase + L0 in-memory, pg_cron refresh раз в N minutes для discovery |
| KuCoin symbol format quirks (`-` vs `/`) | `Symbol.native_symbol` нормализуется в `SymbolRegistry` при `load_markets` |
| Supabase Realtime connection stability | Graceful reconnect в `realtime-py`, fallback на polling в `SupabaseGateway` |
| Large OHLCV responses → context overflow | `ResponseLimitingMiddleware(max_size=500_000)` + background task для `fetch_ohlcv_history` с chunked streaming |
| Supabase local vs cloud drift | `supabase db push` одинаково применяет миграции, контролируется через CI check |

---

## Appendix A — Environment variables (`.env.example`)

```bash
# Supabase
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
SUPABASE_JWT_SECRET=...                    # для phase 2+

# cryptozavr runtime
CRYPTOZAVR_MODE=research_only              # research_only | paper_trading | approval_gated_live
CRYPTOZAVR_LOG_LEVEL=INFO
CRYPTOZAVR_CACHE_TTL_TICKER_SECONDS=5
CRYPTOZAVR_CACHE_TTL_OHLCV_SECONDS=60

# Providers
KUCOIN_API_KEY=                            # пусто в MVP (public endpoints)
KUCOIN_API_SECRET=
KUCOIN_API_PASSPHRASE=
COINGECKO_API_KEY=                         # опционально (free tier без ключа)

# Rate limits
KUCOIN_RATE_LIMIT_RPS=30
COINGECKO_RATE_LIMIT_RPM=30                # free tier
```

## Appendix B — Key dependencies

```toml
# pyproject.toml (excerpt)
[project]
dependencies = [
    "fastmcp>=3.2.4",
    "pydantic>=2.9",
    "pydantic-settings>=2.5",
    "httpx>=0.27",
    "ccxt>=4.4",
    "asyncpg>=0.29",
    "supabase>=2.8",
    "realtime>=2.0",
    "structlog>=24",
    "punq>=0.7",
]

[project.optional-dependencies]
tasks = ["fastmcp[tasks]"]
apps = ["fastmcp[apps]"]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5",
    "pytest-xdist>=3",
    "respx>=0.21",
    "hypothesis>=6.100",
    "polyfactory>=2.18",
    "dirty-equals>=0.8",
    "freezegun>=1.5",
    "ruff>=0.6",
    "mypy>=1.11",
]
```

---

## Appendix C — Glossary

| Term | Meaning |
|------|---------|
| **Envelope** | Форма ответа MCP tool: `{"data": ..., "quality": {...}, "reasoning": {...}}` |
| **Cache-aside** | Паттерн: читать из cache, если miss — из источника + write-back в cache |
| **Hot cache** | Часто читаемые маленькие данные (тикеры). In-memory L0 + Supabase L1. |
| **Warm cache** | Большие данные с умеренной частотой чтения (OHLCV, orderbooks). Supabase L1. |
| **Flyweight** | GoF паттерн разделения shared state (SymbolRegistry) |
| **Decorator chain** | Композиция Decorator-ов вокруг базового объекта |
| **Chain of Responsibility** | GoF паттерн: handlers передают запрос по цепи, каждый решает обрабатывать или пропустить |
| **State pattern** | GoF: поведение объекта меняется в зависимости от состояния (VenueState) |
| **ModeGuard** | Capability-based guard: проверяет, разрешена ли operation в текущем Mode |
| **Capability** | Право на операцию (READ_MARKET_DATA, SUBMIT_LIVE_ORDERS_EXECUTE, ...) |
| **Provenance** | Метаданные о происхождении данных (venue + endpoint) |
| **Staleness** | Шкала свежести: FRESH / RECENT / STALE / EXPIRED |
| **reason_codes** | Массив машиночитаемых меток решений, принятых Chain of Responsibility |
| **Direct server calls** | v3 test pattern: `mcp.call_tool(...)` без Client wrapper |
| **Task (FastMCP)** | `@mcp.tool(task=True)` — background execution с cancel/await/status |

---

## Document status

- **Draft created:** 2026-04-21
- **Next step:** user review → approval → writing-plans skill invocation → implementation plan creation
- **Owner:** cryptozavr brainstorming session
