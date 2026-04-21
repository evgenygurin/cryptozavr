# cryptozavr — Milestone 3.2: Discovery tools

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Four discovery MCP tools — `resolve_symbol`, `list_symbols`, `list_categories`, `scan_trending` — plus two L4 services (`SymbolResolver`, `DiscoveryService`). Extends plugin tool surface from 5 → 9.

**Architecture:** `SymbolResolver` does in-memory fuzzy matching against `SymbolRegistry` (normalize → direct lookup → format variants → base-with-common-quotes) — pg_trgm DB-side fuzzy deferred to M3.3+. `DiscoveryService` is a thin wrapper over `CoinGeckoProvider.list_trending` / `list_categories` (already implemented in M2.3b). Both services hang off `AppState` next to the 4 existing market-data services.

**Tech Stack:** No new deps. Adds 4 MCP tools + 2 services + 3 DTOs.

**Starting tag:** `v0.1.1`. Target: `v0.1.2`.

---

## File Structure

| Path | Responsibility |
|------|---------------|
| `src/cryptozavr/mcp/dtos.py` | MODIFY — add `SymbolDTO`, `TrendingAssetDTO`, `CategoryDTO` |
| `src/cryptozavr/application/services/symbol_resolver.py` | NEW — `SymbolResolver` + result dataclass |
| `src/cryptozavr/application/services/discovery_service.py` | NEW — `DiscoveryService` |
| `src/cryptozavr/mcp/tools/discovery.py` | NEW — registrars for 4 tools |
| `src/cryptozavr/mcp/bootstrap.py` | MODIFY — add 2 services to AppState, extend tuple to 8 |
| `src/cryptozavr/mcp/server.py` | MODIFY — unpack 8-tuple + register new tools |
| `tests/unit/mcp/test_dtos.py` | MODIFY — 3 new DTO tests |
| `tests/unit/application/services/test_symbol_resolver.py` | NEW — 5 tests |
| `tests/unit/application/services/test_discovery_service.py` | NEW — 3 tests |
| `tests/unit/mcp/test_get_symbol_tool.py` | NEW — 3 Client tests (resolve + list) |
| `tests/unit/mcp/test_get_discovery_tool.py` | NEW — 3 Client tests (trending + categories) |

---

## Tasks

### Task 1: Symbol / Asset / Category DTOs

**Files:**
- Modify: `src/cryptozavr/mcp/dtos.py`
- Modify: `tests/unit/mcp/test_dtos.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/unit/mcp/test_dtos.py`:
```python
from cryptozavr.domain.assets import Asset, AssetCategory
from cryptozavr.mcp.dtos import CategoryDTO, SymbolDTO, TrendingAssetDTO

class TestSymbolDTO:
    def test_from_domain_basic_spot_symbol(self) -> None:
        symbol = SymbolRegistry().get(
            VenueId.KUCOIN, "BTC", "USDT",
            market_type=MarketType.SPOT, native_symbol="BTC-USDT",
        )
        dto = SymbolDTO.from_domain(symbol)
        assert dto.venue == "kucoin"
        assert dto.base == "BTC"
        assert dto.quote == "USDT"
        assert dto.native_symbol == "BTC-USDT"
        assert dto.market_type == "spot"

    def test_dto_serializes_to_json(self) -> None:
        symbol = SymbolRegistry().get(
            VenueId.KUCOIN, "ETH", "USDT",
            market_type=MarketType.SPOT, native_symbol="ETH-USDT",
        )
        dto = SymbolDTO.from_domain(symbol)
        payload = dto.model_dump(mode="json")
        assert payload["venue"] == "kucoin"
        assert payload["native_symbol"] == "ETH-USDT"

class TestTrendingAssetDTO:
    def test_from_domain(self) -> None:
        asset = Asset(
            code="BTC",
            name="Bitcoin",
            coingecko_id="bitcoin",
            market_cap_rank=1,
            categories=(AssetCategory.LAYER_1,),
        )
        dto = TrendingAssetDTO.from_domain(asset, rank=0)
        assert dto.code == "BTC"
        assert dto.name == "Bitcoin"
        assert dto.coingecko_id == "bitcoin"
        assert dto.market_cap_rank == 1
        assert dto.categories == ["layer_1"]
        assert dto.rank == 0

class TestCategoryDTO:
    def test_from_dict_core_fields(self) -> None:
        raw = {
            "category_id": "layer-1",
            "name": "Layer 1",
            "market_cap": 1000000000,
            "market_cap_change_24h": 1.5,
        }
        dto = CategoryDTO.from_provider(raw)
        assert dto.id == "layer-1"
        assert dto.name == "Layer 1"
        assert dto.market_cap == 1000000000
        assert dto.market_cap_change_24h_pct == 1.5

    def test_missing_optional_fields_become_none(self) -> None:
        raw = {"category_id": "meme", "name": "Meme"}
        dto = CategoryDTO.from_provider(raw)
        assert dto.market_cap is None
        assert dto.market_cap_change_24h_pct is None
```

Update the top imports in `test_dtos.py` to include `Asset`, `AssetCategory`, `CategoryDTO`, `SymbolDTO`, `TrendingAssetDTO`.

- [ ] **Step 2: FAIL**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/mcp/test_dtos.py -v 2>&1 | tail -10
```

- [ ] **Step 3: Implement**

Read current `src/cryptozavr/mcp/dtos.py` to see existing imports. Append AFTER `TradesDTO` (SINGLE Write call to avoid formatter stripping new imports):

Add to top imports:
```python
from cryptozavr.domain.assets import Asset
from cryptozavr.domain.symbols import Symbol
```

Append three classes:
```python
class SymbolDTO(BaseModel):
    """Wire-format market symbol."""

    model_config = ConfigDict(frozen=True)

    venue: str
    base: str
    quote: str
    native_symbol: str
    market_type: str

    @classmethod
    def from_domain(cls, symbol: Symbol) -> SymbolDTO:
        return cls(
            venue=symbol.venue.value,
            base=symbol.base,
            quote=symbol.quote,
            native_symbol=symbol.native_symbol,
            market_type=symbol.market_type.value,
        )

class TrendingAssetDTO(BaseModel):
    """Wire-format trending crypto asset (from CoinGecko)."""

    model_config = ConfigDict(frozen=True)

    code: str
    name: str | None
    coingecko_id: str | None
    market_cap_rank: int | None
    categories: list[str]
    rank: int

    @classmethod
    def from_domain(cls, asset: Asset, rank: int) -> TrendingAssetDTO:
        return cls(
            code=asset.code,
            name=asset.name,
            coingecko_id=asset.coingecko_id,
            market_cap_rank=asset.market_cap_rank,
            categories=[c.value for c in asset.categories],
            rank=rank,
        )

class CategoryDTO(BaseModel):
    """Wire-format CoinGecko category."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    market_cap: Decimal | None = None
    market_cap_change_24h_pct: Decimal | None = None

    @classmethod
    def from_provider(cls, raw: dict[str, Any]) -> CategoryDTO:
        mc = raw.get("market_cap")
        mc_change = raw.get("market_cap_change_24h")
        return cls(
            id=str(raw["category_id"]),
            name=str(raw["name"]),
            market_cap=Decimal(str(mc)) if mc is not None else None,
            market_cap_change_24h_pct=(
                Decimal(str(mc_change)) if mc_change is not None else None
            ),
        )
```

(If `from typing import Any` not at top — add it.)

- [ ] **Step 4: PASS**

```bash
uv run pytest tests/unit/mcp/test_dtos.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src
uv run pytest tests/unit tests/contract -m "not integration" -q 2>&1 | tail -3
```
Expect: 308 prior + 5 new = 313.

- [ ] **Step 5: Commit**

Write commit to /tmp/commit-msg.txt:
```bash
feat(mcp): add SymbolDTO + TrendingAssetDTO + CategoryDTO

Three wire-format DTOs for the upcoming discovery tools. SymbolDTO:
venue/base/quote/native/market_type. TrendingAssetDTO wraps Asset +
a rank field (0-indexed position in CoinGecko trending response).
CategoryDTO reads CoinGecko's `/coins/categories` dict response.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/mcp/dtos.py tests/unit/mcp/test_dtos.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 2: `SymbolResolver` service

**Files:**
- Create: `src/cryptozavr/application/services/symbol_resolver.py`
- Create: `tests/unit/application/services/test_symbol_resolver.py`

- [ ] **Step 1: Write failing tests**

Write `tests/unit/application/services/test_symbol_resolver.py`:
```python
"""Test SymbolResolver: in-memory fuzzy match against SymbolRegistry."""

from __future__ import annotations

import pytest

from cryptozavr.application.services.symbol_resolver import SymbolResolver
from cryptozavr.domain.exceptions import SymbolNotFoundError, VenueNotSupportedError
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId

@pytest.fixture
def registry() -> SymbolRegistry:
    reg = SymbolRegistry()
    reg.get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )
    reg.get(
        VenueId.KUCOIN, "ETH", "USDT",
        market_type=MarketType.SPOT, native_symbol="ETH-USDT",
    )
    return reg

class TestSymbolResolver:
    def test_exact_native_symbol_resolves_direct(
        self, registry: SymbolRegistry,
    ) -> None:
        resolver = SymbolResolver(registry)
        sym = resolver.resolve(user_input="BTC-USDT", venue="kucoin")
        assert sym.native_symbol == "BTC-USDT"

    def test_lowercase_normalized_to_upper(
        self, registry: SymbolRegistry,
    ) -> None:
        resolver = SymbolResolver(registry)
        sym = resolver.resolve(user_input="btc-usdt", venue="kucoin")
        assert sym.native_symbol == "BTC-USDT"

    def test_concatenated_form_resolves_via_variants(
        self, registry: SymbolRegistry,
    ) -> None:
        # "BTCUSDT" → try BTC-USDT, BTC/USDT via quote-suffix split
        resolver = SymbolResolver(registry)
        sym = resolver.resolve(user_input="btcusdt", venue="kucoin")
        assert sym.native_symbol == "BTC-USDT"

    def test_base_only_resolves_with_default_quote(
        self, registry: SymbolRegistry,
    ) -> None:
        # "BTC" → falls back to (BTC, USDT) base lookup
        resolver = SymbolResolver(registry)
        sym = resolver.resolve(user_input="BTC", venue="kucoin")
        assert sym.native_symbol == "BTC-USDT"

    def test_unknown_venue_raises(self, registry: SymbolRegistry) -> None:
        resolver = SymbolResolver(registry)
        with pytest.raises(VenueNotSupportedError):
            resolver.resolve(user_input="BTC-USDT", venue="binance")

    def test_unknown_symbol_raises(self, registry: SymbolRegistry) -> None:
        resolver = SymbolResolver(registry)
        with pytest.raises(SymbolNotFoundError):
            resolver.resolve(user_input="DOGE-USDT", venue="kucoin")
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement (SINGLE Write)**

Write `src/cryptozavr/application/services/symbol_resolver.py`:
```python
"""SymbolResolver — fuzzy user-input → Symbol (in-memory MVP).

Algorithm:
1. Resolve venue (string → VenueId, check it's known).
2. Normalise input: strip + upper.
3. Direct `registry.find(venue, native_symbol=normalized)`.
4. Try format variants: strip separators, split by common quote suffix,
   re-assemble with `-` / `/` / `""`.
5. Fall back to base-only lookup with default quotes (USDT, USD, BTC).
6. Raise SymbolNotFoundError if nothing matched.

pg_trgm DB-side fuzzy (for Bitcoin / bitcoin aliases) is deferred to
M3.3+ once SupabaseGateway exposes alias queries.
"""

from __future__ import annotations

from cryptozavr.domain.exceptions import (
    SymbolNotFoundError,
    VenueNotSupportedError,
)
from cryptozavr.domain.symbols import Symbol, SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId

_DEFAULT_QUOTES: tuple[str, ...] = ("USDT", "USD", "BTC", "ETH")
_SEPARATORS: tuple[str, ...] = ("-", "/", "")

class SymbolResolver:
    """Translate any user input into a Symbol on a given venue."""

    def __init__(self, registry: SymbolRegistry) -> None:
        self._registry = registry

    def resolve(self, *, user_input: str, venue: str) -> Symbol:
        venue_id = self._resolve_venue(venue)
        normalised = user_input.strip().upper()

        # 1. Direct native_symbol hit.
        direct = self._registry.find(venue_id, normalised)
        if direct is not None:
            return direct

        # 2. Format variants (separator permutations, concatenated form).
        for candidate in self._variants(normalised):
            sym = self._registry.find(venue_id, candidate)
            if sym is not None:
                return sym

        # 3. Base-only → try common quotes.
        for quote in _DEFAULT_QUOTES:
            sym = self._registry.find_by_base(
                venue_id, normalised, quote=quote, market_type=MarketType.SPOT,
            )
            if sym is not None:
                return sym
            # Handle already-concatenated bases: "BTCUSDT" → base="BTC".
            if normalised.endswith(quote) and len(normalised) > len(quote):
                base = normalised[: -len(quote)]
                sym = self._registry.find_by_base(
                    venue_id, base, quote=quote, market_type=MarketType.SPOT,
                )
                if sym is not None:
                    return sym

        raise SymbolNotFoundError(user_input=user_input, venue=venue)

    @staticmethod
    def _resolve_venue(venue: str) -> VenueId:
        try:
            return VenueId(venue)
        except ValueError as exc:
            raise VenueNotSupportedError(venue=venue) from exc

    @staticmethod
    def _variants(normalised: str) -> list[str]:
        """Return plausible native_symbol forms for `normalised`."""
        out: set[str] = set()
        # Try splitting on existing separators first.
        for sep in ("-", "/"):
            if sep in normalised:
                base, _, quote = normalised.partition(sep)
                for other in _SEPARATORS:
                    out.add(f"{base}{other}{quote}")
        # Try quote-suffix split (concatenated form).
        for quote in _DEFAULT_QUOTES:
            if normalised.endswith(quote) and len(normalised) > len(quote):
                base = normalised[: -len(quote)]
                for sep in _SEPARATORS:
                    out.add(f"{base}{sep}{quote}")
        out.discard(normalised)
        return sorted(out)
```

- [ ] **Step 4: PASS**

```bash
uv run pytest tests/unit/application/services/test_symbol_resolver.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src
uv run pytest tests/unit tests/contract -m "not integration" -q 2>&1 | tail -3
```
Expect: 6 new + 313 = 319.

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```text
feat(app): add SymbolResolver service

In-memory fuzzy user-input → Symbol via SymbolRegistry. 3-step
cascade: direct native_symbol hit → format variants (separator
permutations + concatenated-form split on known quote suffixes) →
base-only lookup with default quotes (USDT, USD, BTC, ETH). Unknown
venue → VenueNotSupportedError; nothing matched →
SymbolNotFoundError. pg_trgm DB-side fuzzy deferred to M3.3+.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/application/services/symbol_resolver.py \
    tests/unit/application/services/test_symbol_resolver.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 3: `DiscoveryService` (wraps CoinGecko)

**Files:**
- Create: `src/cryptozavr/application/services/discovery_service.py`
- Create: `tests/unit/application/services/test_discovery_service.py`

- [ ] **Step 1: Write failing tests**

Write `tests/unit/application/services/test_discovery_service.py`:
```python
"""Test DiscoveryService: thin wrapper over CoinGeckoProvider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from cryptozavr.application.services.discovery_service import DiscoveryService
from cryptozavr.domain.assets import Asset, AssetCategory

@pytest.fixture
def coingecko_provider():
    provider = MagicMock()
    provider.list_trending = AsyncMock(
        return_value=[
            Asset(
                code="BTC",
                name="Bitcoin",
                coingecko_id="bitcoin",
                market_cap_rank=1,
                categories=(AssetCategory.LAYER_1,),
            ),
            Asset(
                code="PEPE",
                name="Pepe",
                coingecko_id="pepe",
                market_cap_rank=30,
                categories=(AssetCategory.MEME,),
            ),
        ],
    )
    provider.list_categories = AsyncMock(
        return_value=[
            {
                "category_id": "layer-1",
                "name": "Layer 1",
                "market_cap": 1_500_000_000,
                "market_cap_change_24h": 2.0,
            },
            {
                "category_id": "meme",
                "name": "Meme",
                "market_cap": 50_000_000,
                "market_cap_change_24h": -3.0,
            },
        ],
    )
    return provider

class TestDiscoveryService:
    @pytest.mark.asyncio
    async def test_list_trending_returns_assets(self, coingecko_provider):
        service = DiscoveryService(coingecko=coingecko_provider)
        assets = await service.list_trending(limit=2)
        assert len(assets) == 2
        assert assets[0].code == "BTC"
        coingecko_provider.list_trending.assert_awaited_once_with(limit=2)

    @pytest.mark.asyncio
    async def test_list_categories_returns_raw_dicts(
        self, coingecko_provider,
    ):
        service = DiscoveryService(coingecko=coingecko_provider)
        cats = await service.list_categories(limit=2)
        assert len(cats) == 2
        assert cats[0]["category_id"] == "layer-1"
        coingecko_provider.list_categories.assert_awaited_once_with(limit=2)

    @pytest.mark.asyncio
    async def test_default_limits_applied(self, coingecko_provider):
        service = DiscoveryService(coingecko=coingecko_provider)
        await service.list_trending()
        await service.list_categories()
        # defaults: trending=15, categories=30 (match CoinGeckoProvider defaults)
        coingecko_provider.list_trending.assert_awaited_with(limit=15)
        coingecko_provider.list_categories.assert_awaited_with(limit=30)
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

Write `src/cryptozavr/application/services/discovery_service.py`:
```python
"""DiscoveryService — thin L4 wrapper over CoinGecko list_trending/list_categories."""

from __future__ import annotations

from typing import Any

from cryptozavr.domain.assets import Asset

class DiscoveryService:
    """Fetches trending + categories from the CoinGecko provider.

    No cache, no decoration — the CoinGecko provider itself sits behind
    the factory-wrapped decorator chain (Retry/RateLimit/Caching/Logging).
    """

    def __init__(self, *, coingecko: Any) -> None:
        self._coingecko = coingecko

    async def list_trending(self, *, limit: int = 15) -> list[Asset]:
        return await self._coingecko.list_trending(limit=limit)

    async def list_categories(self, *, limit: int = 30) -> list[dict[str, Any]]:
        return await self._coingecko.list_categories(limit=limit)
```

- [ ] **Step 4: PASS**

```bash
uv run pytest tests/unit/application/services/test_discovery_service.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src
```
Expect: 3 new + prior = 322.

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```text
feat(app): add DiscoveryService

Thin L4 facade over CoinGeckoProvider.list_trending + list_categories.
No cache, no decoration — the underlying provider is already factory-
wrapped with Retry/RateLimit/Caching/Logging. Default limits match
the provider (trending=15, categories=30).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/application/services/discovery_service.py \
    tests/unit/application/services/test_discovery_service.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 4: `resolve_symbol` + `list_symbols` MCP tools

**Files:**
- Create: `src/cryptozavr/mcp/tools/discovery.py`
- Create: `tests/unit/mcp/test_get_symbol_tool.py`

- [ ] **Step 1: Write failing tests**

Write `tests/unit/mcp/test_get_symbol_tool.py`:
```python
"""In-memory Client tests for resolve_symbol + list_symbols."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from cryptozavr.domain.exceptions import SymbolNotFoundError
from cryptozavr.domain.symbols import Symbol, SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.mcp.tools.discovery import (
    register_list_symbols_tool,
    register_resolve_symbol_tool,
)

@dataclass(slots=True)
class _AppState:
    symbol_resolver: object
    registry: SymbolRegistry

def _btc() -> Symbol:
    return SymbolRegistry().get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )

def _build_server(resolver, registry) -> FastMCP:
    @asynccontextmanager
    async def lifespan(server):
        yield _AppState(symbol_resolver=resolver, registry=registry)

    mcp = FastMCP(name="test", version="0.0.0", lifespan=lifespan)
    register_resolve_symbol_tool(mcp)
    register_list_symbols_tool(mcp)
    return mcp

@pytest.mark.asyncio
async def test_resolve_symbol_returns_dto() -> None:
    resolver = MagicMock()
    resolver.resolve = MagicMock(return_value=_btc())
    registry = SymbolRegistry()
    mcp = _build_server(resolver, registry)
    async with Client(mcp) as client:
        result = await client.call_tool(
            "resolve_symbol",
            {"user_input": "btc", "venue": "kucoin"},
        )
    payload = result.structured_content
    assert payload["native_symbol"] == "BTC-USDT"
    assert payload["base"] == "BTC"
    resolver.resolve.assert_called_once_with(
        user_input="btc", venue="kucoin",
    )

@pytest.mark.asyncio
async def test_resolve_symbol_not_found_surfaces_tool_error() -> None:
    resolver = MagicMock()
    resolver.resolve = MagicMock(
        side_effect=SymbolNotFoundError(user_input="DOGE", venue="kucoin"),
    )
    mcp = _build_server(resolver, SymbolRegistry())
    async with Client(mcp) as client:
        with pytest.raises(ToolError) as exc_info:
            await client.call_tool(
                "resolve_symbol",
                {"user_input": "DOGE", "venue": "kucoin"},
            )
    assert "DOGE" in str(exc_info.value)

@pytest.mark.asyncio
async def test_list_symbols_returns_all_for_venue() -> None:
    registry = SymbolRegistry()
    registry.get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )
    registry.get(
        VenueId.KUCOIN, "ETH", "USDT",
        market_type=MarketType.SPOT, native_symbol="ETH-USDT",
    )
    mcp = _build_server(resolver=MagicMock(), registry=registry)
    async with Client(mcp) as client:
        result = await client.call_tool(
            "list_symbols", {"venue": "kucoin"},
        )
    payload = result.structured_content
    assert payload["venue"] == "kucoin"
    assert len(payload["symbols"]) == 2
    native = {s["native_symbol"] for s in payload["symbols"]}
    assert native == {"BTC-USDT", "ETH-USDT"}
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement (SINGLE Write)**

Write `src/cryptozavr/mcp/tools/discovery.py`:
```python
"""Discovery MCP tools: resolve_symbol, list_symbols, scan_trending, list_categories."""

from __future__ import annotations

from typing import Annotated, Any, cast

from fastmcp import Context, FastMCP
from pydantic import BaseModel, ConfigDict, Field

from cryptozavr.application.services.discovery_service import DiscoveryService
from cryptozavr.application.services.symbol_resolver import SymbolResolver
from cryptozavr.domain.exceptions import DomainError
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import VenueId
from cryptozavr.mcp.dtos import CategoryDTO, SymbolDTO, TrendingAssetDTO
from cryptozavr.mcp.errors import domain_to_tool_error

class SymbolListDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    venue: str
    symbols: list[SymbolDTO]

class TrendingListDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    assets: list[TrendingAssetDTO]

class CategoryListDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    categories: list[CategoryDTO]

def register_resolve_symbol_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        name="resolve_symbol",
        description=(
            "Fuzzy-match a user's symbol string (e.g. 'btc', 'BTCUSDT', "
            "'BTC-USDT') against the SymbolRegistry for a venue."
        ),
        tags={"discovery", "public", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def resolve_symbol(
        user_input: Annotated[str, Field(description="Any user string.")],
        venue: Annotated[str, Field(description="Venue id: kucoin, coingecko.")],
        ctx: Context,
    ) -> SymbolDTO:
        resolver = cast(
            SymbolResolver,
            cast(Any, ctx.lifespan_context).symbol_resolver,
        )
        try:
            symbol = resolver.resolve(user_input=user_input, venue=venue)
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc
        return SymbolDTO.from_domain(symbol)

def register_list_symbols_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        name="list_symbols",
        description=(
            "List all registered symbols for a venue. MVP: in-memory "
            "SymbolRegistry only — seeded venues (kucoin, coingecko)."
        ),
        tags={"discovery", "public", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def list_symbols(
        venue: Annotated[str, Field(description="Venue id.")],
        ctx: Context,
    ) -> SymbolListDTO:
        registry = cast(
            SymbolRegistry,
            cast(Any, ctx.lifespan_context).registry,
        )
        try:
            venue_id = VenueId(venue)
        except ValueError as exc:
            raise domain_to_tool_error(
                __import__(
                    "cryptozavr.domain.exceptions",
                    fromlist=["VenueNotSupportedError"],
                ).VenueNotSupportedError(venue=venue),
            ) from exc
        symbols = [
            SymbolDTO.from_domain(sym)
            for sym in registry.all_for_venue(venue_id)
        ]
        return SymbolListDTO(venue=venue, symbols=symbols)

def register_scan_trending_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        name="scan_trending",
        description="List currently trending crypto assets (CoinGecko).",
        tags={"discovery", "public", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def scan_trending(
        ctx: Context,
        limit: Annotated[
            int,
            Field(ge=1, le=50, description="How many trending coins (1..50)."),
        ] = 15,
    ) -> TrendingListDTO:
        discovery = cast(
            DiscoveryService,
            cast(Any, ctx.lifespan_context).discovery_service,
        )
        assets = await discovery.list_trending(limit=limit)
        return TrendingListDTO(
            assets=[
                TrendingAssetDTO.from_domain(a, rank=i)
                for i, a in enumerate(assets)
            ],
        )

def register_list_categories_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        name="list_categories",
        description="List CoinGecko asset categories with market cap.",
        tags={"discovery", "public", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def list_categories(
        ctx: Context,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="How many categories (1..100)."),
        ] = 30,
    ) -> CategoryListDTO:
        discovery = cast(
            DiscoveryService,
            cast(Any, ctx.lifespan_context).discovery_service,
        )
        raw = await discovery.list_categories(limit=limit)
        return CategoryListDTO(
            categories=[CategoryDTO.from_provider(c) for c in raw],
        )
```

IMPORTANT: `SymbolRegistry.all_for_venue(venue_id)` may not exist — verify and add if missing (Task 4a below).

- [ ] **Step 3a: Add `SymbolRegistry.all_for_venue` if missing**

Check `src/cryptozavr/domain/symbols.py` for `all_for_venue`. If not present, add:
```python
    def all_for_venue(self, venue: VenueId) -> list[Symbol]:
        """Return all symbols registered for a venue (stable order by native_symbol)."""
        with self._lock:
            return sorted(
                (s for s in self._store.values() if s.venue == venue),
                key=lambda s: s.native_symbol,
            )
```

And add a quick unit test in `tests/unit/domain/test_symbols.py` (append if file exists, otherwise skip — the integration through list_symbols tool test already covers it).

- [ ] **Step 4: PASS (3 new tests + 1 new domain test if added)**

```bash
uv run pytest tests/unit/mcp/test_get_symbol_tool.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src
uv run pytest tests/unit tests/contract -m "not integration" -q 2>&1 | tail -3
```

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```bash
feat(mcp): add resolve_symbol + list_symbols tools

Two discovery MCP tools + SymbolListDTO wrapper. resolve_symbol
delegates to SymbolResolver (fuzzy match → Symbol). list_symbols
reads the in-memory registry and returns all symbols for a venue,
stable-sorted by native_symbol. Both declare read-only/idempotent
annotations and surface DomainError → ToolError via the mapper.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/mcp/tools/discovery.py \
    src/cryptozavr/domain/symbols.py \
    tests/unit/mcp/test_get_symbol_tool.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 5: `scan_trending` + `list_categories` tools

**Files:**
- Create: `tests/unit/mcp/test_get_discovery_tool.py`

(Tool registrars already in `src/cryptozavr/mcp/tools/discovery.py` from Task 4 — just need tests.)

- [ ] **Step 1: Write failing tests**

Write `tests/unit/mcp/test_get_discovery_tool.py`:
```python
"""In-memory Client tests for scan_trending + list_categories."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import Client, FastMCP

from cryptozavr.domain.assets import Asset, AssetCategory
from cryptozavr.mcp.tools.discovery import (
    register_list_categories_tool,
    register_scan_trending_tool,
)

@dataclass(slots=True)
class _AppState:
    discovery_service: object

def _build_server(service) -> FastMCP:
    @asynccontextmanager
    async def lifespan(server):
        yield _AppState(discovery_service=service)

    mcp = FastMCP(name="test", version="0.0.0", lifespan=lifespan)
    register_scan_trending_tool(mcp)
    register_list_categories_tool(mcp)
    return mcp

@pytest.mark.asyncio
async def test_scan_trending_returns_ranked_list() -> None:
    service = MagicMock()
    service.list_trending = AsyncMock(
        return_value=[
            Asset(
                code="BTC", name="Bitcoin", coingecko_id="bitcoin",
                market_cap_rank=1, categories=(AssetCategory.LAYER_1,),
            ),
            Asset(
                code="PEPE", name="Pepe", coingecko_id="pepe",
                market_cap_rank=30, categories=(AssetCategory.MEME,),
            ),
        ],
    )
    mcp = _build_server(service)
    async with Client(mcp) as client:
        result = await client.call_tool("scan_trending", {"limit": 2})
    payload = result.structured_content
    assert len(payload["assets"]) == 2
    assert payload["assets"][0]["code"] == "BTC"
    assert payload["assets"][0]["rank"] == 0
    assert payload["assets"][1]["rank"] == 1

@pytest.mark.asyncio
async def test_list_categories_returns_categories() -> None:
    service = MagicMock()
    service.list_categories = AsyncMock(
        return_value=[
            {
                "category_id": "layer-1", "name": "Layer 1",
                "market_cap": 1_000_000_000, "market_cap_change_24h": 2.5,
            },
            {
                "category_id": "meme", "name": "Meme",
                "market_cap": 50_000_000, "market_cap_change_24h": -1.2,
            },
        ],
    )
    mcp = _build_server(service)
    async with Client(mcp) as client:
        result = await client.call_tool("list_categories", {"limit": 2})
    payload = result.structured_content
    assert len(payload["categories"]) == 2
    assert payload["categories"][0]["id"] == "layer-1"
    assert payload["categories"][0]["market_cap"] == "1000000000"

@pytest.mark.asyncio
async def test_scan_trending_default_limit_is_15() -> None:
    service = MagicMock()
    service.list_trending = AsyncMock(return_value=[])
    mcp = _build_server(service)
    async with Client(mcp) as client:
        await client.call_tool("scan_trending", {})
    service.list_trending.assert_awaited_once_with(limit=15)
```

- [ ] **Step 2: FAIL** (if `discovery.py` missing the registrars).

- [ ] **Step 3: Should already pass** (registrars added in Task 4).

```bash
uv run pytest tests/unit/mcp/test_get_discovery_tool.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src
```

- [ ] **Step 4: Commit**

Write to /tmp/commit-msg.txt:
```bash
test(mcp): add scan_trending + list_categories Client tests

Covers: ranked asset list (rank=0, 1, …) from TrendingAssetDTO;
category dicts → CategoryDTO with Decimal market cap preserved
through JSON serialization; default limit=15 for scan_trending.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add tests/unit/mcp/test_get_discovery_tool.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 6: Wire services into bootstrap + server

**Files:**
- Modify: `src/cryptozavr/mcp/bootstrap.py`
- Modify: `src/cryptozavr/mcp/server.py`

- [ ] **Step 1: Update bootstrap.py**

Read current bootstrap first to confirm structure. Then apply these changes:

1. Add imports alongside existing services:
```python
from cryptozavr.application.services.discovery_service import DiscoveryService
from cryptozavr.application.services.symbol_resolver import SymbolResolver
```

2. Extend `AppState` to carry new fields + the shared registry:
```python
@dataclass(slots=True)
class AppState:
    """Lifespan-scoped application state exposed to tools."""

    ticker_service: TickerService
    ohlcv_service: OhlcvService
    order_book_service: OrderBookService
    trades_service: TradesService
    subscriber: RealtimeSubscriber
    symbol_resolver: SymbolResolver
    discovery_service: DiscoveryService
    registry: SymbolRegistry
```

3. Update `build_production_service` return type to a larger tuple (now 9-tuple — the original 6 + SymbolResolver + DiscoveryService + SymbolRegistry):
```python
async def build_production_service(
    settings: Settings,
) -> tuple[
    TickerService,
    OhlcvService,
    OrderBookService,
    TradesService,
    RealtimeSubscriber,
    SymbolResolver,
    DiscoveryService,
    SymbolRegistry,
    Callable[[], Awaitable[None]],
]:
```

4. Keep `registry` (the existing `SymbolRegistry`) and after constructing subscriber, build the two new services:
```python
    symbol_resolver = SymbolResolver(registry)
    discovery_service = DiscoveryService(
        coingecko=providers[VenueId.COINGECKO],
    )
```

5. Update the return tuple:
```python
    return (
        ticker_service,
        ohlcv_service,
        order_book_service,
        trades_service,
        subscriber,
        symbol_resolver,
        discovery_service,
        registry,
        cleanup,
    )
```

- [ ] **Step 2: Update server.py**

Read current server.py. Apply:

1. Add imports:
```python
from cryptozavr.mcp.tools.discovery import (
    register_list_categories_tool,
    register_list_symbols_tool,
    register_resolve_symbol_tool,
    register_scan_trending_tool,
)
```

2. Update lifespan to unpack 9-tuple + yield extended AppState:
```python
    @asynccontextmanager
    async def lifespan(
        _server: FastMCP[AppState],
    ) -> AsyncIterator[AppState]:
        (
            ticker_service,
            ohlcv_service,
            order_book_service,
            trades_service,
            subscriber,
            symbol_resolver,
            discovery_service,
            registry,
            cleanup,
        ) = await build_production_service(settings)
        _LOGGER.info(
            "cryptozavr-research started",
            extra={"mode": settings.mode.value, "version": __version__},
        )
        try:
            yield AppState(
                ticker_service=ticker_service,
                ohlcv_service=ohlcv_service,
                order_book_service=order_book_service,
                trades_service=trades_service,
                subscriber=subscriber,
                symbol_resolver=symbol_resolver,
                discovery_service=discovery_service,
                registry=registry,
            )
        finally:
            await cleanup()
```

3. Register new tools after existing ones:
```python
    _register_echo(mcp)
    register_ticker_tool(mcp)
    register_ohlcv_tool(mcp)
    register_order_book_tool(mcp)
    register_trades_tool(mcp)
    register_resolve_symbol_tool(mcp)
    register_list_symbols_tool(mcp)
    register_scan_trending_tool(mcp)
    register_list_categories_tool(mcp)
```

- [ ] **Step 3: Smoke checks**

```bash
cd /Users/laptop/dev/cryptozavr
uv run ruff check . && uv run ruff format --check . && uv run mypy src
uv run pytest tests/unit tests/contract -m "not integration" -q 2>&1 | tail -3
```

- [ ] **Step 4: Commit**

Write to /tmp/commit-msg.txt:
```bash
feat(mcp): wire SymbolResolver + DiscoveryService + 4 discovery tools

AppState now carries 7 services + the SymbolRegistry (for list_symbols
direct reads). build_production_service returns a 9-tuple. Server
lifespan unpacks and yields AppState; registers 4 new tools
(resolve_symbol, list_symbols, scan_trending, list_categories).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/mcp/bootstrap.py src/cryptozavr/mcp/server.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 7: Slash-commands + SessionStart banner update

**Files:**
- Create: `commands/resolve.md`
- Create: `commands/trending.md`
- Modify: `hooks/session-start.sh`

- [ ] **Step 1: Write `commands/resolve.md`**

```markdown
---
description: Resolve a user-input symbol string (fuzzy) to a canonical venue symbol.
argument-hint: <user_input> [venue]
allowed-tools: ["mcp__plugin_cryptozavr_cryptozavr-research__resolve_symbol"]
---

Resolve the user's input to a canonical symbol on the requested venue.

Parse `$ARGUMENTS` as `<user_input> [venue]`. If `venue` is omitted, default to `kucoin`.

Call `resolve_symbol` with those values. Render:
- `native_symbol` (bold)
- `base` / `quote` pair
- `market_type`

If the tool surfaces a SymbolNotFoundError, tell the user it wasn't found and suggest `/cryptozavr:trending` or `list_symbols` for discovery.
```

- [ ] **Step 2: Write `commands/trending.md`**

```markdown
---
description: List currently trending crypto assets (CoinGecko) with ranks + market cap ranks.
argument-hint: "[limit=15]"
allowed-tools:
  - "mcp__plugin_cryptozavr_cryptozavr-research__scan_trending"
  - "mcp__plugin_cryptozavr_cryptozavr-research__list_categories"
---

Show the user the current CoinGecko trending list.

Parse `$ARGUMENTS` as `[limit]` (default 15, max 50).

Call `scan_trending(limit=limit)`. Present a compact table:
- rank | code | name | market_cap_rank | categories

If the user asks "what's hot in DeFi / memes / L1" and similar, follow up by calling `list_categories` to show sector-level market cap changes.
```

- [ ] **Step 3: Update `hooks/session-start.sh`**

Read current banner, then update command list:
```bash
#!/usr/bin/env bash
set -euo pipefail

cat <<'EOF'
# cryptozavr plugin loaded

Slash commands:
  /cryptozavr:ticker <venue> <symbol>              — fetch latest ticker
  /cryptozavr:ohlcv <venue> <symbol> <timeframe>   — OHLCV candles
  /cryptozavr:research <venue> <symbol>            — 4-tool research collage
  /cryptozavr:resolve <user_input> [venue]         — fuzzy symbol lookup
  /cryptozavr:trending [limit]                     — CoinGecko trending assets
  /cryptozavr:health                               — MCP server smoke test

Subagent: crypto-researcher (for multi-step market research)

Venues seeded: kucoin, coingecko
9 MCP tools: echo, get_ticker, get_ohlcv, get_order_book, get_trades,
             resolve_symbol, list_symbols, scan_trending, list_categories.
EOF
```

- [ ] **Step 4: Smoke check + validate plugin manifest**

```bash
cd /Users/laptop/dev/cryptozavr
bash hooks/session-start.sh | head -3
claude plugin validate /Users/laptop/dev/cryptozavr
uv run pytest tests/unit tests/contract -m "not integration" -q 2>&1 | tail -3
```

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```text
feat(plugin): add /cryptozavr:resolve + /cryptozavr:trending commands

Two new slash-commands on top of the discovery tool family:
/cryptozavr:resolve wraps resolve_symbol (fuzzy symbol lookup).
/cryptozavr:trending wraps scan_trending. SessionStart banner updated
to list 6 commands + 9 MCP tools (up from 4/5).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add commands/resolve.md commands/trending.md hooks/session-start.sh
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 8: CHANGELOG + tag v0.1.2 + push

- [ ] **Step 1: Verify**

```bash
cd /Users/laptop/dev/cryptozavr
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest tests/unit tests/contract -m "not integration" -q 2>&1 | tail -3
```
Expect: ~326 unit + 5 contract.

- [ ] **Step 2: Update CHANGELOG**

Edit `/Users/laptop/dev/cryptozavr/CHANGELOG.md`. Find:
```markdown
## [Unreleased]

## [0.1.1] - 2026-04-22
```

Replace with:
```markdown
## [Unreleased]

## [0.1.2] - 2026-04-22

### Added — M3.2 Discovery tools
- `SymbolResolver` (L4 service) — fuzzy user-input → Symbol via SymbolRegistry. Normalise → direct → format variants → base+default quotes.
- `DiscoveryService` (L4 service) — thin CoinGecko wrapper (list_trending, list_categories).
- `SymbolDTO`, `TrendingAssetDTO`, `CategoryDTO` + `SymbolListDTO`/`TrendingListDTO`/`CategoryListDTO` wrappers.
- 4 new MCP tools: `resolve_symbol`, `list_symbols`, `scan_trending`, `list_categories`. Plugin tool surface: **9 tools** (echo + 4 market-data + 4 discovery).
- 2 new slash-commands: `/cryptozavr:resolve`, `/cryptozavr:trending`.
- `SymbolRegistry.all_for_venue()` — sorted in-memory enumeration.
- AppState: +3 fields (`symbol_resolver`, `discovery_service`, `registry`). `build_production_service` returns 9-tuple.
- ~17 new unit tests. Total ~325 unit + 5 contract.

### Next
- M3.3: Analytics MCP tools on top of MarketAnalyzer (analyze_snapshot, compute_vwap, identify_support_resistance, volatility_regime).
- M3.4: fetch_ohlcv_history streaming + SessionExplainer envelope → tag v0.2.0 (MVP closure).

## [0.1.1] - 2026-04-22
```

- [ ] **Step 3: Commit CHANGELOG + plan**

```bash
cd /Users/laptop/dev/cryptozavr
git add CHANGELOG.md
git add docs/superpowers/plans/2026-04-22-cryptozavr-m3.2-discovery-tools.md 2>/dev/null || true
```

Write to /tmp/commit-msg.txt:
```bash
docs: finalize CHANGELOG for v0.1.2 (M3.2 Discovery tools)

Symbol resolution + CoinGecko trending/categories surfaced as 4 new
MCP tools. Plugin tool surface expanded from 5 to 9.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

- [ ] **Step 4: Tag + push**

Write to /tmp/tag-msg.txt:
```text
M3.2 Discovery tools complete

SymbolResolver + DiscoveryService + 4 MCP tools (resolve_symbol,
list_symbols, scan_trending, list_categories) + 2 slash-commands.
Plugin tool surface: 9 tools. 17 new unit tests.
```

```bash
cd /Users/laptop/dev/cryptozavr
git tag -a v0.1.2 -F /tmp/tag-msg.txt
rm /tmp/tag-msg.txt
git push origin main
git push origin v0.1.2
```

- [ ] **Step 5: Summary**

```bash
cd /Users/laptop/dev/cryptozavr
echo "=== M3.2 complete ==="
git log --oneline v0.1.1..HEAD
git tag -l | tail -5
```

---

## Acceptance Criteria

1. ✅ 8 tasks done. 4 new MCP tools + 2 services + 3 DTOs + 2 slash-commands.
2. ✅ ~17 new unit tests. Total ≥325 unit + 5 contract + 14 integration (skip-safe).
3. ✅ `resolve_symbol("btc", "kucoin")` returns BTC-USDT (seeded venue).
4. ✅ `list_symbols("kucoin")` returns sorted by native_symbol.
5. ✅ `scan_trending` / `list_categories` call CoinGeckoProvider and return DTOs.
6. ✅ SessionStart banner lists 6 commands + 9 tools.
7. ✅ `claude plugin validate` passes.
8. ✅ Mypy strict + ruff + pytest green.
9. ✅ Tag `v0.1.2` pushed.

---

## Notes

- **MVP fuzzy = in-memory.** `SymbolResolver` uses the registry alone — no DB calls. pg_trgm queries over `symbol_aliases` deferred to M3.3+ when we wire `SupabaseGateway.query_aliases()`.
- **Trending is non-cached.** CoinGecko trending updates every ~10 minutes upstream; the decorator chain's in-memory caching (already configured with shorter TTL for trending-like endpoints) handles hot paths.
- **AppState now carries `SymbolRegistry` directly.** Needed for `list_symbols` without an extra service wrapper. Slight Law-of-Demeter trade-off vs. a `DiscoveryService.list_symbols` method — kept it inline for now; extract if a second caller appears.
- **Bootstrap tuple grows to 9.** At this point consider refactoring `build_production_service` to return a single `AppState` directly instead of a tuple (pre-M3.3 refactor; not scoped here to keep M3.2 focused).
- **`list_symbols` limits**: returns ALL symbols — fine while registry is tiny. When registry grows DB-backed in phase 2, add pagination.
