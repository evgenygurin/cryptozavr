# cryptozavr — Milestone 2.4: First MCP tool `get_ticker` (full stack) Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Первый real MCP tool `get_ticker(venue, symbol, force_refresh) -> TickerDTO` через полный стек: Client → FastMCP → Application `TickerService` → Chain of Responsibility → Decorator chain → Provider → SupabaseGateway (cache-aside).

**Architecture:** Добавляется слой L4 Application (`TickerService` как Facade над Chain+Factory+Gateway). MCP-слой инжектит service через FastMCP `lifespan` (v3 API), tool закрытие читает service из `ctx.request_context.lifespan_context`. Domain exceptions конвертируются в `fastmcp.exceptions.ToolError` через `mcp/errors.py`. In-memory тесты через `Client(mcp)`.

**Tech Stack:** Python 3.12, FastMCP 3.2.4, pydantic v2, pytest-asyncio. No new deps.

**Starting tag:** `v0.0.6`. Target: `v0.0.7`.

---

## File Structure

| Path | Responsibility |
|------|---------------|
| `src/cryptozavr/application/services/__init__.py` | Package marker |
| `src/cryptozavr/application/services/ticker_service.py` | `TickerService` + `TickerFetchResult` (L4 orchestrator) |
| `src/cryptozavr/mcp/dtos.py` | `TickerDTO` (Pydantic BaseModel) + `from_domain` factory |
| `src/cryptozavr/mcp/errors.py` | `domain_to_tool_error` mapper |
| `src/cryptozavr/mcp/tools/__init__.py` | Package marker |
| `src/cryptozavr/mcp/tools/ticker.py` | `register_ticker_tool(mcp)` |
| `src/cryptozavr/mcp/bootstrap.py` | `AppState`, `build_production_service` (wiring всей инфры) |
| `src/cryptozavr/mcp/server.py` | MODIFY — новая `build_server(lifespan)` подпись, tool registration, new `main()` |
| `tests/unit/application/services/test_ticker_service.py` | TickerService unit tests |
| `tests/unit/mcp/test_dtos.py` | TickerDTO unit tests |
| `tests/unit/mcp/test_errors.py` | Error mapper unit tests |
| `tests/unit/mcp/test_get_ticker_tool.py` | In-memory `Client(mcp)` tool tests |

---

## Tasks

### Task 1: `TickerDTO` Pydantic model

**Files:**
- Create: `src/cryptozavr/mcp/dtos.py`
- Create: `tests/unit/mcp/__init__.py` (empty)
- Create: `tests/unit/mcp/test_dtos.py`

- [ ] **Step 1: Write failing tests**

Write empty `tests/unit/mcp/__init__.py`.

Write `tests/unit/mcp/test_dtos.py`:
```python
"""Test TickerDTO construction and from_domain factory."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.domain.market_data import Ticker
from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.mcp.dtos import TickerDTO

@pytest.fixture
def btc_ticker() -> Ticker:
    symbol = SymbolRegistry().get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )
    return Ticker(
        symbol=symbol,
        last=Decimal("50000.5"),
        bid=Decimal("50000.0"),
        ask=Decimal("50001.0"),
        volume_24h=Decimal("1234.5"),
        observed_at=Instant.from_ms(1_700_000_000_000),
        quality=DataQuality(
            source=Provenance(venue_id="kucoin", endpoint="fetch_ticker"),
            fetched_at=Instant.from_ms(1_700_000_000_000),
            staleness=Staleness.FRESH,
            confidence=Confidence.HIGH,
            cache_hit=False,
        ),
    )

class TestTickerDTO:
    def test_from_domain_copies_core_fields(self, btc_ticker: Ticker) -> None:
        dto = TickerDTO.from_domain(btc_ticker, reason_codes=["venue:healthy"])
        assert dto.venue == "kucoin"
        assert dto.symbol == "BTC-USDT"
        assert dto.last == Decimal("50000.5")
        assert dto.bid == Decimal("50000.0")
        assert dto.ask == Decimal("50001.0")
        assert dto.volume_24h == Decimal("1234.5")
        assert dto.observed_at_ms == 1_700_000_000_000
        assert dto.staleness == "fresh"
        assert dto.confidence == "high"
        assert dto.cache_hit is False
        assert dto.reason_codes == ["venue:healthy"]

    def test_from_domain_handles_missing_optional_fields(
        self, btc_ticker: Ticker,
    ) -> None:
        stripped = btc_ticker.__class__(
            symbol=btc_ticker.symbol,
            last=btc_ticker.last,
            observed_at=btc_ticker.observed_at,
            quality=btc_ticker.quality,
        )
        dto = TickerDTO.from_domain(stripped, reason_codes=[])
        assert dto.bid is None
        assert dto.ask is None
        assert dto.volume_24h is None

    def test_dto_serializes_to_json(self, btc_ticker: Ticker) -> None:
        dto = TickerDTO.from_domain(btc_ticker, reason_codes=["cache:hit"])
        payload = dto.model_dump(mode="json")
        assert payload["venue"] == "kucoin"
        assert payload["symbol"] == "BTC-USDT"
        assert payload["last"] == "50000.5"  # Decimal → str in JSON mode
        assert payload["reason_codes"] == ["cache:hit"]
```

- [ ] **Step 2: Run — FAIL**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/mcp/test_dtos.py -v
```
Expected: ModuleNotFoundError on `cryptozavr.mcp.dtos`.

- [ ] **Step 3: Implement**

Write `src/cryptozavr/mcp/dtos.py`:
```python
"""MCP-facing DTOs. Pydantic models for tool return types."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from cryptozavr.domain.market_data import Ticker

class TickerDTO(BaseModel):
    """Wire-format ticker for the get_ticker MCP tool."""

    model_config = ConfigDict(frozen=True)

    venue: str
    symbol: str
    last: Decimal
    bid: Decimal | None = None
    ask: Decimal | None = None
    volume_24h: Decimal | None = None
    observed_at_ms: int
    staleness: str
    confidence: str
    cache_hit: bool
    reason_codes: list[str]

    @classmethod
    def from_domain(cls, ticker: Ticker, reason_codes: list[str]) -> TickerDTO:
        return cls(
            venue=ticker.symbol.venue.value,
            symbol=ticker.symbol.native_symbol,
            last=ticker.last,
            bid=ticker.bid,
            ask=ticker.ask,
            volume_24h=ticker.volume_24h,
            observed_at_ms=ticker.observed_at.to_ms(),
            staleness=ticker.quality.staleness.name.lower(),
            confidence=ticker.quality.confidence.name.lower(),
            cache_hit=ticker.quality.cache_hit,
            reason_codes=list(reason_codes),
        )
```

- [ ] **Step 4: PASS (3 tests).**

```bash
uv run pytest tests/unit/mcp/test_dtos.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src
```

- [ ] **Step 5: Commit**

Write message to /tmp/commit-msg.txt:
```text
feat(mcp): add TickerDTO wire format

Pydantic BaseModel with from_domain factory. Includes reason_codes
list so the chain's audit trail flows to the MCP client alongside
the ticker payload.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

Then:
```bash
git add src/cryptozavr/mcp/dtos.py tests/unit/mcp/__init__.py tests/unit/mcp/test_dtos.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 2: `domain_to_tool_error` mapper

**Files:**
- Create: `src/cryptozavr/mcp/errors.py`
- Create: `tests/unit/mcp/test_errors.py`

- [ ] **Step 1: Write failing tests**

Write `tests/unit/mcp/test_errors.py`:
```python
"""Test Domain → ToolError mapping."""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError

from cryptozavr.domain.exceptions import (
    DomainError,
    ProviderUnavailableError,
    RateLimitExceededError,
    SymbolNotFoundError,
    ValidationError,
    VenueNotSupportedError,
)
from cryptozavr.mcp.errors import domain_to_tool_error

class TestDomainToToolError:
    def test_symbol_not_found_maps_to_clear_message(self) -> None:
        exc = SymbolNotFoundError(user_input="XYZ-ABC", venue="kucoin")
        err = domain_to_tool_error(exc)
        assert isinstance(err, ToolError)
        assert "XYZ-ABC" in str(err)
        assert "kucoin" in str(err)

    def test_venue_not_supported_mentions_venue(self) -> None:
        exc = VenueNotSupportedError(venue="binance")
        err = domain_to_tool_error(exc)
        assert "binance" in str(err)

    def test_rate_limit_suggests_retry(self) -> None:
        exc = RateLimitExceededError("kucoin backoff")
        err = domain_to_tool_error(exc)
        assert "rate limit" in str(err).lower()

    def test_provider_unavailable_is_retriable(self) -> None:
        exc = ProviderUnavailableError("network")
        err = domain_to_tool_error(exc)
        assert "unavailable" in str(err).lower()

    def test_validation_error_preserves_message(self) -> None:
        exc = ValidationError("negative limit")
        err = domain_to_tool_error(exc)
        assert "negative limit" in str(err)

    def test_unknown_domain_error_falls_back_to_str(self) -> None:
        class _OddDomainError(DomainError):
            pass

        exc = _OddDomainError("weird")
        err = domain_to_tool_error(exc)
        assert "weird" in str(err)
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

Write `src/cryptozavr/mcp/errors.py`:
```python
"""Map domain exceptions to fastmcp ToolError with user-facing messages."""

from __future__ import annotations

from fastmcp.exceptions import ToolError

from cryptozavr.domain.exceptions import (
    DomainError,
    ProviderUnavailableError,
    RateLimitExceededError,
    SymbolNotFoundError,
    ValidationError,
    VenueNotSupportedError,
)

def domain_to_tool_error(exc: DomainError) -> ToolError:
    """Convert a domain exception into a client-facing ToolError."""
    if isinstance(exc, SymbolNotFoundError):
        return ToolError(
            f"Symbol {exc.user_input!r} not found on venue {exc.venue!r}.",
        )
    if isinstance(exc, VenueNotSupportedError):
        return ToolError(
            f"Venue {exc.venue!r} is not supported by this server.",
        )
    if isinstance(exc, RateLimitExceededError):
        return ToolError(
            "Upstream rate limit exceeded. Please retry in a few seconds.",
        )
    if isinstance(exc, ProviderUnavailableError):
        return ToolError(
            "Upstream provider is unavailable. Please retry later.",
        )
    if isinstance(exc, ValidationError):
        return ToolError(f"Invalid input: {exc}")
    return ToolError(str(exc))
```

- [ ] **Step 4: PASS (6 tests).**

```bash
uv run pytest tests/unit/mcp/test_errors.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src
```

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```text
feat(mcp): add domain-to-ToolError mapper

Translates each Domain exception family into a user-facing ToolError
message. Unknown subclasses fall back to str(exc). Keeps domain errors
out of the MCP wire protocol and gives callers retryable vs fatal hints.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/mcp/errors.py tests/unit/mcp/test_errors.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 3: `TickerService` (L4 Application orchestrator)

**Files:**
- Create: `src/cryptozavr/application/services/__init__.py`
- Create: `src/cryptozavr/application/services/ticker_service.py`
- Create: `tests/unit/application/__init__.py` (if absent)
- Create: `tests/unit/application/services/__init__.py`
- Create: `tests/unit/application/services/test_ticker_service.py`

- [ ] **Step 1: Write failing tests**

Write empty `tests/unit/application/__init__.py` (create only if missing) and `tests/unit/application/services/__init__.py`.

Write `tests/unit/application/services/test_ticker_service.py`:
```python
"""Test TickerService: venue/symbol validation + chain wiring + fetch result."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from cryptozavr.application.services.ticker_service import (
    TickerFetchResult,
    TickerService,
)
from cryptozavr.domain.exceptions import (
    SymbolNotFoundError,
    VenueNotSupportedError,
)
from cryptozavr.domain.market_data import Ticker
from cryptozavr.domain.quality import (
    Confidence,
    DataQuality,
    Provenance,
    Staleness,
)
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

def _make_ticker(symbol) -> Ticker:
    return Ticker(
        symbol=symbol,
        last=Decimal("100"),
        observed_at=Instant.now(),
        quality=DataQuality(
            source=Provenance(venue_id="kucoin", endpoint="fetch_ticker"),
            fetched_at=Instant.now(),
            staleness=Staleness.FRESH,
            confidence=Confidence.HIGH,
            cache_hit=False,
        ),
    )

@pytest.fixture
def registry() -> SymbolRegistry:
    reg = SymbolRegistry()
    reg.get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )
    return reg

@pytest.fixture
def provider_factory_output(registry: SymbolRegistry):
    """Build a provider whose fetch_ticker returns a canned Ticker."""
    symbol = registry.find(VenueId.KUCOIN, "BTC-USDT")
    assert symbol is not None
    provider = MagicMock()
    provider.fetch_ticker = AsyncMock(return_value=_make_ticker(symbol))
    return provider

@pytest.fixture
def gateway():
    gw = MagicMock()
    gw.load_ticker = AsyncMock(return_value=None)  # cache miss by default
    gw.upsert_ticker = AsyncMock()
    return gw

@pytest.fixture
def service(registry, gateway, provider_factory_output) -> TickerService:
    return TickerService(
        registry=registry,
        venue_states={VenueId.KUCOIN: VenueState(VenueId.KUCOIN)},
        providers={VenueId.KUCOIN: provider_factory_output},
        gateway=gateway,
    )

class TestTickerService:
    @pytest.mark.asyncio
    async def test_fetch_ticker_returns_fetch_result_with_reasons(
        self, service: TickerService,
    ) -> None:
        result = await service.fetch_ticker(venue="kucoin", symbol="BTC-USDT")
        assert isinstance(result, TickerFetchResult)
        assert result.ticker.last == Decimal("100")
        assert "venue:healthy" in result.reason_codes
        assert "provider:called" in result.reason_codes

    @pytest.mark.asyncio
    async def test_cache_hit_skips_provider(
        self, registry, gateway, provider_factory_output,
    ) -> None:
        symbol = registry.find(VenueId.KUCOIN, "BTC-USDT")
        assert symbol is not None
        cached = _make_ticker(symbol)
        gateway.load_ticker = AsyncMock(return_value=cached)
        service = TickerService(
            registry=registry,
            venue_states={VenueId.KUCOIN: VenueState(VenueId.KUCOIN)},
            providers={VenueId.KUCOIN: provider_factory_output},
            gateway=gateway,
        )
        result = await service.fetch_ticker(venue="kucoin", symbol="BTC-USDT")
        assert result.ticker is cached
        assert "cache:hit" in result.reason_codes
        provider_factory_output.fetch_ticker.assert_not_called()

    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_cache(
        self, registry, gateway, provider_factory_output,
    ) -> None:
        symbol = registry.find(VenueId.KUCOIN, "BTC-USDT")
        assert symbol is not None
        gateway.load_ticker = AsyncMock(return_value=_make_ticker(symbol))
        service = TickerService(
            registry=registry,
            venue_states={VenueId.KUCOIN: VenueState(VenueId.KUCOIN)},
            providers={VenueId.KUCOIN: provider_factory_output},
            gateway=gateway,
        )
        result = await service.fetch_ticker(
            venue="kucoin", symbol="BTC-USDT", force_refresh=True,
        )
        assert "cache:bypassed" in result.reason_codes
        provider_factory_output.fetch_ticker.assert_awaited_once()
        gateway.load_ticker.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_venue_string_raises_venue_not_supported(
        self, service: TickerService,
    ) -> None:
        with pytest.raises(VenueNotSupportedError):
            await service.fetch_ticker(venue="binance", symbol="BTC-USDT")

    @pytest.mark.asyncio
    async def test_unknown_symbol_raises_symbol_not_found(
        self, service: TickerService,
    ) -> None:
        with pytest.raises(SymbolNotFoundError):
            await service.fetch_ticker(venue="kucoin", symbol="DOGE-USDT")
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

Write `src/cryptozavr/application/services/__init__.py`:
```python
"""Application services (L4): use-case orchestration."""
```

Write `src/cryptozavr/application/services/ticker_service.py`:
```python
"""TickerService: orchestrates chain + factory + gateway for ticker fetches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cryptozavr.domain.exceptions import (
    SymbolNotFoundError,
    VenueNotSupportedError,
)
from cryptozavr.domain.market_data import Ticker
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import VenueId
from cryptozavr.infrastructure.providers.chain.assembly import (
    build_ticker_chain,
)
from cryptozavr.infrastructure.providers.chain.context import (
    FetchContext,
    FetchOperation,
    FetchRequest,
)
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

@dataclass(frozen=True, slots=True)
class TickerFetchResult:
    """Ticker + audit trail (reason codes) from the chain."""

    ticker: Ticker
    reason_codes: list[str]

class TickerService:
    """Facade: translates (venue, symbol) input into a chain run."""

    def __init__(
        self,
        *,
        registry: SymbolRegistry,
        venue_states: dict[VenueId, VenueState],
        providers: dict[VenueId, Any],
        gateway: Any,
    ) -> None:
        self._registry = registry
        self._venue_states = venue_states
        self._providers = providers
        self._gateway = gateway

    async def fetch_ticker(
        self, *, venue: str, symbol: str, force_refresh: bool = False,
    ) -> TickerFetchResult:
        venue_id = self._resolve_venue(venue)
        symbol_obj = self._registry.find(venue_id, symbol)
        if symbol_obj is None:
            raise SymbolNotFoundError(user_input=symbol, venue=venue)

        chain = build_ticker_chain(
            state=self._venue_states[venue_id],
            registry=self._registry,
            gateway=self._gateway,
            provider=self._providers[venue_id],
        )
        ctx = FetchContext(
            request=FetchRequest(
                operation=FetchOperation.TICKER,
                symbol=symbol_obj,
                force_refresh=force_refresh,
            ),
        )
        result = await chain.handle(ctx)
        ticker: Ticker = result.metadata["result"]
        return TickerFetchResult(
            ticker=ticker,
            reason_codes=list(result.reason_codes),
        )

    def _resolve_venue(self, venue: str) -> VenueId:
        try:
            venue_id = VenueId(venue)
        except ValueError as exc:
            raise VenueNotSupportedError(venue=venue) from exc
        if venue_id not in self._venue_states:
            raise VenueNotSupportedError(venue=venue)
        return venue_id
```

- [ ] **Step 4: PASS (5 tests).**

```bash
uv run pytest tests/unit/application -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src
```

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```bash
feat(app): add TickerService L4 orchestrator

Facade over Chain of Responsibility + Factory + SupabaseGateway.
Validates venue/symbol against runtime registries, builds the 5-handler
chain per request, and returns TickerFetchResult (ticker + reason_codes
audit trail). Unknown venue or symbol surfaces as domain exception for
MCP-layer translation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/application/services/__init__.py \
    src/cryptozavr/application/services/ticker_service.py \
    tests/unit/application/services/__init__.py \
    tests/unit/application/services/test_ticker_service.py
# also add tests/unit/application/__init__.py if it was newly created:
git add tests/unit/application/__init__.py 2>/dev/null || true
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 4: MCP `get_ticker` tool + in-memory Client tests

**Files:**
- Create: `src/cryptozavr/mcp/tools/__init__.py`
- Create: `src/cryptozavr/mcp/tools/ticker.py`
- Create: `tests/unit/mcp/test_get_ticker_tool.py`

- [ ] **Step 1: Write failing tests**

Write `tests/unit/mcp/test_get_ticker_tool.py`:
```python
"""In-memory Client(mcp) tests for the get_ticker tool."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from cryptozavr.application.services.ticker_service import (
    TickerFetchResult,
)
from cryptozavr.domain.exceptions import SymbolNotFoundError
from cryptozavr.domain.market_data import Ticker
from cryptozavr.domain.quality import (
    Confidence,
    DataQuality,
    Provenance,
    Staleness,
)
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.mcp.tools.ticker import register_ticker_tool

@dataclass(slots=True)
class _AppState:
    ticker_service: object

def _make_ticker() -> Ticker:
    symbol = SymbolRegistry().get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )
    return Ticker(
        symbol=symbol,
        last=Decimal("100"),
        observed_at=Instant.from_ms(1_700_000_000_000),
        quality=DataQuality(
            source=Provenance(venue_id="kucoin", endpoint="fetch_ticker"),
            fetched_at=Instant.from_ms(1_700_000_000_000),
            staleness=Staleness.FRESH,
            confidence=Confidence.HIGH,
            cache_hit=False,
        ),
    )

def _build_server(mock_service) -> FastMCP:
    @asynccontextmanager
    async def lifespan(server):
        yield _AppState(ticker_service=mock_service)

    mcp = FastMCP(name="test", version="0.0.0", lifespan=lifespan)
    register_ticker_tool(mcp)
    return mcp

@pytest.mark.asyncio
async def test_get_ticker_returns_dto_fields() -> None:
    service = MagicMock()
    service.fetch_ticker = AsyncMock(
        return_value=TickerFetchResult(
            ticker=_make_ticker(),
            reason_codes=["venue:healthy", "cache:miss", "provider:called"],
        ),
    )
    mcp = _build_server(service)
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_ticker", {"venue": "kucoin", "symbol": "BTC-USDT"},
        )
    payload = result.data
    assert payload["venue"] == "kucoin"
    assert payload["symbol"] == "BTC-USDT"
    assert payload["last"] == "100"
    assert payload["reason_codes"] == [
        "venue:healthy", "cache:miss", "provider:called",
    ]
    service.fetch_ticker.assert_awaited_once_with(
        venue="kucoin", symbol="BTC-USDT", force_refresh=False,
    )

@pytest.mark.asyncio
async def test_get_ticker_forwards_force_refresh() -> None:
    service = MagicMock()
    service.fetch_ticker = AsyncMock(
        return_value=TickerFetchResult(
            ticker=_make_ticker(), reason_codes=["cache:bypassed"],
        ),
    )
    mcp = _build_server(service)
    async with Client(mcp) as client:
        await client.call_tool(
            "get_ticker",
            {"venue": "kucoin", "symbol": "BTC-USDT", "force_refresh": True},
        )
    service.fetch_ticker.assert_awaited_once_with(
        venue="kucoin", symbol="BTC-USDT", force_refresh=True,
    )

@pytest.mark.asyncio
async def test_symbol_not_found_surfaces_as_tool_error() -> None:
    service = MagicMock()
    service.fetch_ticker = AsyncMock(
        side_effect=SymbolNotFoundError(user_input="DOGE-USDT", venue="kucoin"),
    )
    mcp = _build_server(service)
    async with Client(mcp) as client:
        with pytest.raises(ToolError) as exc_info:
            await client.call_tool(
                "get_ticker", {"venue": "kucoin", "symbol": "DOGE-USDT"},
            )
    assert "DOGE-USDT" in str(exc_info.value)
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

Write `src/cryptozavr/mcp/tools/__init__.py`:
```python
"""MCP tool registration modules. One module per tool family."""
```

Write `src/cryptozavr/mcp/tools/ticker.py`:
```python
"""get_ticker MCP tool registration."""

from __future__ import annotations

from typing import Annotated

from fastmcp import Context, FastMCP
from pydantic import Field

from cryptozavr.application.services.ticker_service import TickerService
from cryptozavr.domain.exceptions import DomainError
from cryptozavr.mcp.dtos import TickerDTO
from cryptozavr.mcp.errors import domain_to_tool_error

def register_ticker_tool(mcp: FastMCP) -> None:
    """Attach get_ticker tool to the given FastMCP instance."""

    @mcp.tool(
        name="get_ticker",
        description=(
            "Fetch the latest ticker (last, bid, ask, 24h volume) for a "
            "symbol on a venue. Goes through venue-health → symbol-exists "
            "→ staleness-bypass → supabase-cache → provider-fetch chain. "
            "Set force_refresh=True to skip the cache."
        ),
        tags={"market", "public", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_ticker(
        venue: Annotated[
            str,
            Field(description="Venue id. Supported: kucoin, coingecko."),
        ],
        symbol: Annotated[
            str,
            Field(description="Native symbol, e.g. BTC-USDT (kucoin)."),
        ],
        ctx: Context,
        force_refresh: Annotated[
            bool,
            Field(description="Bypass the Supabase cache."),
        ] = False,
    ) -> TickerDTO:
        service: TickerService = (
            ctx.request_context.lifespan_context.ticker_service
        )
        try:
            result = await service.fetch_ticker(
                venue=venue, symbol=symbol, force_refresh=force_refresh,
            )
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc
        return TickerDTO.from_domain(result.ticker, result.reason_codes)
```

- [ ] **Step 4: PASS (3 tests).**

```bash
uv run pytest tests/unit/mcp/test_get_ticker_tool.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src
```

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```bash
feat(mcp): add get_ticker tool

Registers the first real MCP tool. Reads TickerService from
lifespan_context, catches DomainError → ToolError, returns TickerDTO
with reason_codes audit trail. Covered by in-memory Client(mcp) tests
with a MagicMock service (DTO mapping + force_refresh + error path).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/mcp/tools/__init__.py \
    src/cryptozavr/mcp/tools/ticker.py \
    tests/unit/mcp/test_get_ticker_tool.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 5: Production bootstrap (`build_production_service`)

**Files:**
- Create: `src/cryptozavr/mcp/bootstrap.py`

No unit tests — this is thin wiring exercised by the manual smoke test in Task 7 (and, eventually, by integration tests in M2.5 once cloud Supabase is wired up).

- [ ] **Step 1: Inspect actual Supabase gateway + pool signatures**

```bash
cd /Users/laptop/dev/cryptozavr
grep -n "class SupabaseGateway\|def __init__\|async def open\|async def close" \
  src/cryptozavr/infrastructure/supabase/gateway.py
grep -n "class PgPoolConfig\|async def create_pool\|dsn" \
  src/cryptozavr/infrastructure/supabase/pg_pool.py
```

Adjust the code in Step 2 if argument names differ.

- [ ] **Step 2: Implement**

Write `src/cryptozavr/mcp/bootstrap.py`:
```python
"""Production wiring for the MCP server.

Creates infrastructure (HTTP, rate limiters, symbol registry, venue states,
gateway, providers), assembles a TickerService, and returns a cleanup
coroutine the caller must await on shutdown.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from cryptozavr.application.services.ticker_service import TickerService
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.factory import ProviderFactory
from cryptozavr.infrastructure.providers.http import HttpClientRegistry
from cryptozavr.infrastructure.providers.rate_limiters import (
    RateLimiterRegistry,
)
from cryptozavr.infrastructure.providers.state.venue_state import VenueState
from cryptozavr.infrastructure.supabase.gateway import SupabaseGateway
from cryptozavr.infrastructure.supabase.pg_pool import (
    PgPoolConfig,
    create_pool,
)
from cryptozavr.mcp.settings import Settings

_LOG = logging.getLogger(__name__)

@dataclass(slots=True)
class AppState:
    """Lifespan-scoped application state exposed to tools."""

    ticker_service: TickerService

async def build_production_service(
    settings: Settings,
) -> tuple[TickerService, Callable[[], Awaitable[None]]]:
    """Build a production TickerService and a cleanup coroutine."""
    http_registry = HttpClientRegistry()

    rate_registry = RateLimiterRegistry()
    rate_registry.register("kucoin", rate_per_sec=30.0, capacity=30)
    rate_registry.register("coingecko", rate_per_sec=0.5, capacity=30)

    registry = SymbolRegistry()
    # MVP seed — extend to DB-driven in M2.5+.
    registry.get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )
    registry.get(
        VenueId.KUCOIN, "ETH", "USDT",
        market_type=MarketType.SPOT, native_symbol="ETH-USDT",
    )

    venue_states = {
        VenueId.KUCOIN: VenueState(VenueId.KUCOIN),
        VenueId.COINGECKO: VenueState(VenueId.COINGECKO),
    }

    pg_pool = await create_pool(PgPoolConfig(dsn=settings.supabase_db_url))
    gateway = SupabaseGateway(
        pg_pool=pg_pool,
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_service_role_key,
    )

    factory = ProviderFactory(
        http_registry=http_registry, rate_registry=rate_registry,
    )
    providers = {
        VenueId.KUCOIN: factory.create_kucoin(
            state=venue_states[VenueId.KUCOIN],
        ),
        VenueId.COINGECKO: await factory.create_coingecko(
            state=venue_states[VenueId.COINGECKO],
        ),
    }

    service = TickerService(
        registry=registry,
        venue_states=venue_states,
        providers=providers,
        gateway=gateway,
    )

    async def cleanup() -> None:
        _LOG.info("cryptozavr shutting down")
        try:
            await http_registry.close_all()
        except Exception as exc:  # noqa: BLE001
            _LOG.warning("http registry close failed: %s", exc)
        try:
            await gateway.close()
        except Exception as exc:  # noqa: BLE001
            _LOG.warning("gateway close failed: %s", exc)
        try:
            await pg_pool.close()
        except Exception as exc:  # noqa: BLE001
            _LOG.warning("pg pool close failed: %s", exc)

    return service, cleanup
```

**Adjust** the `SupabaseGateway(...)` and `PgPoolConfig(...)` constructor calls to match the actual signatures you inspected in Step 1. If a signature is materially different, keep the behaviour (construct gateway, close everything on cleanup) but use the real argument names.

- [ ] **Step 3: Smoke checks**

```bash
cd /Users/laptop/dev/cryptozavr
uv run ruff check . && uv run ruff format --check . && uv run mypy src
uv run pytest tests/unit -q 2>&1 | tail -3
```

All clean; no new tests.

- [ ] **Step 4: Commit**

Write to /tmp/commit-msg.txt:
```text
feat(mcp): add production bootstrap

build_production_service wires HTTP + rate registries, seeds
SymbolRegistry with BTC-USDT and ETH-USDT on KuCoin, creates per-venue
VenueState, opens SupabaseGateway, builds ProviderFactory-wrapped
providers, and assembles TickerService. Returns a cleanup coroutine the
MCP lifespan awaits on shutdown.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/mcp/bootstrap.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 6: Rewire `server.py` with lifespan + tool registration

**Files:**
- Modify: `src/cryptozavr/mcp/server.py`

- [ ] **Step 1: Read the current file**

```bash
cd /Users/laptop/dev/cryptozavr
cat src/cryptozavr/mcp/server.py
```

- [ ] **Step 2: Replace the entire file contents**

Overwrite `src/cryptozavr/mcp/server.py` with:
```python
"""FastMCP server bootstrap: echo + get_ticker.

Uses FastMCP v3 lifespan to own TickerService lifecycle.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from cryptozavr import __version__
from cryptozavr.mcp.bootstrap import AppState, build_production_service
from cryptozavr.mcp.settings import Settings
from cryptozavr.mcp.tools.ticker import register_ticker_tool

_LOGGER = logging.getLogger(__name__)

def _register_echo(mcp: FastMCP[AppState]) -> None:
    @mcp.tool(
        name="echo",
        description=(
            "Smoke-test tool. Returns the provided message with server "
            "version. Useful for verifying plugin load and dispatch."
        ),
        tags={"smoke", "mvp", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    def echo(
        message: Annotated[str, Field(description="Any string to echo back.")],
    ) -> dict[str, str]:
        """Echo the input message with server version metadata."""
        return {"message": message, "version": __version__}

def build_server(settings: Settings) -> FastMCP[AppState]:
    """Build the FastMCP server with production lifespan."""

    @asynccontextmanager
    async def lifespan(
        _server: FastMCP[AppState],
    ) -> AsyncIterator[AppState]:
        service, cleanup = await build_production_service(settings)
        _LOGGER.info(
            "cryptozavr-research started",
            extra={"mode": settings.mode.value, "version": __version__},
        )
        try:
            yield AppState(ticker_service=service)
        finally:
            await cleanup()

    mcp: FastMCP[AppState] = FastMCP(
        name="cryptozavr-research",
        version=__version__,
        lifespan=lifespan,
    )
    _register_echo(mcp)
    register_ticker_tool(mcp)
    return mcp

def main() -> None:
    """Entrypoint for `python -m cryptozavr.mcp.server` and console_scripts."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    settings = Settings()  # type: ignore[call-arg]
    mcp = build_server(settings)
    mcp.run()  # STDIO default

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Smoke check**

```bash
cd /Users/laptop/dev/cryptozavr
uv run ruff check . && uv run ruff format --check . && uv run mypy src
uv run pytest tests/unit tests/contract -m "not integration" -q 2>&1 | tail -3
```

Expected: clean; all prior tests still pass (≥240 total after Tasks 1–4).

- [ ] **Step 4: Commit**

Write to /tmp/commit-msg.txt:
```bash
feat(mcp): wire lifespan + get_ticker into build_server

Replaces the M1 echo-only server with a FastMCP v3 lifespan that owns
TickerService and cleans up HTTP/gateway/pg_pool on shutdown. Echo
stays for smoke-testing; get_ticker is the first real tool. Generic
parameter FastMCP[AppState] documents the lifespan context type.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/mcp/server.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 7: Manual smoke test (optional, documented)

Document the manual verification in `docs/superpowers/m2.4-smoke-test.md` so the next user (or future you) can reproduce it. No automated test — the lifespan needs a live Supabase, and we're staying skip-safe.

**Files:**
- Create: `docs/superpowers/m2.4-smoke-test.md`

- [ ] **Step 1: Write the smoke-test note**

Write `docs/superpowers/m2.4-smoke-test.md`:
```markdown
# M2.4 Manual smoke test — get_ticker

## Prereqs
- Local Supabase running: `supabase start`
- Env: `.env` with `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_URL`
- Migrations applied: `supabase db reset` (or `supabase db push`)

## Steps

1. Start the MCP server over STDIO:
   ```
   uv run python -m cryptozavr.mcp.server
   ```
   The process reads MCP JSON-RPC on stdin and writes on stdout.

2. From another terminal, use `fastmcp` CLI or a minimal Python client:
   ```python
   import asyncio
   from fastmcp import Client

   async def main():
       async with Client("python -m cryptozavr.mcp.server") as client:
           tools = await client.list_tools()
           print([t.name for t in tools])  # ['echo', 'get_ticker']
           result = await client.call_tool(
               "get_ticker", {"venue": "kucoin", "symbol": "BTC-USDT"},
           )
           print(result.data)
   asyncio.run(main())
   ```

3. Expected: first call returns reason_codes including `cache:miss` and
   `provider:called`; second call within ~5s returns `cache:hit`.

## What this verifies
- Lifespan opens all infra (HTTP pool, rate limiters, pg pool, supabase).
- Full stack: chain → decorators → provider → write-through.
- Cleanup: server exits without dangling httpx clients.
```

- [ ] **Step 2: Commit**

Write to /tmp/commit-msg.txt:
```bash
docs: add M2.4 smoke-test note

Manual verification steps for get_ticker round-trip against a local
Supabase. Documented because automated end-to-end requires live infra
(deferred to integration suite in M2.5+).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add docs/superpowers/m2.4-smoke-test.md
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 8: CHANGELOG + tag v0.0.7 + push

- [ ] **Step 1: Verify full suite green**

```bash
cd /Users/laptop/dev/cryptozavr
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest tests/unit tests/contract -m "not integration" -v 2>&1 | tail -10
```

Expected: all clean; ≥245 unit + 5 contract tests passing.

- [ ] **Step 2: Update CHANGELOG**

Edit `/Users/laptop/dev/cryptozavr/CHANGELOG.md`. Find:
```markdown
## [Unreleased]

## [0.0.6] - 2026-04-21
```

Replace the `[Unreleased]` line with:
```markdown
## [Unreleased]

## [0.0.7] - 2026-04-21

### Added — M2.4 First MCP tool `get_ticker` (full stack)
- `TickerDTO` (Pydantic): wire format with `venue`, `symbol`, `last`, `bid`, `ask`, `volume_24h`, `observed_at_ms`, `staleness`, `confidence`, `cache_hit`, `reason_codes`. `from_domain` factory.
- `domain_to_tool_error`: maps `SymbolNotFoundError` / `VenueNotSupportedError` / `RateLimitExceededError` / `ProviderUnavailableError` / `ValidationError` / generic `DomainError` into user-facing `fastmcp.exceptions.ToolError`.
- `TickerService` (L4 Application orchestrator): validates venue/symbol, builds the 5-handler chain per request, returns `TickerFetchResult` (ticker + reason codes). Unknown venue or symbol raises the matching domain exception.
- `register_ticker_tool(mcp)`: `get_ticker(venue, symbol, force_refresh)` reads `TickerService` from `ctx.request_context.lifespan_context`, catches `DomainError`, returns `TickerDTO`.
- `build_production_service(settings)`: wires `HttpClientRegistry`, `RateLimiterRegistry` (kucoin 30 rps, coingecko 0.5 rps), `SymbolRegistry` seeded with BTC-USDT + ETH-USDT on KuCoin, per-venue `VenueState`, `SupabaseGateway` over asyncpg pool, `ProviderFactory`-wrapped KuCoin + CoinGecko providers. Returns `(service, cleanup)`.
- `build_server(settings)` now owns a FastMCP v3 `lifespan` that opens and closes all infra around `TickerService`.
- Manual smoke-test note: `docs/superpowers/m2.4-smoke-test.md`.
- ~17 new unit tests (TickerDTO 3 + errors 6 + TickerService 5 + get_ticker tool 3).

### Next
- M2.5: second tool (`get_ohlcv`) + Realtime subscribe stub + integration tests against live Supabase.

## [0.0.6] - 2026-04-21
```

- [ ] **Step 3: Commit CHANGELOG + plan**

```bash
cd /Users/laptop/dev/cryptozavr
git add CHANGELOG.md
git add docs/superpowers/plans/2026-04-21-cryptozavr-m2.4-first-mcp-tool.md 2>/dev/null || true
```

Write to /tmp/commit-msg.txt:
```bash
docs: finalize CHANGELOG for v0.0.7 (M2.4 first MCP tool)

Completes the first real MCP tool get_ticker through the full stack:
Client → FastMCP → TickerService → Chain → Factory → Provider →
Supabase cache-aside.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

- [ ] **Step 4: Tag + push**

Write tag message to /tmp/tag-msg.txt:
```bash
M2.4 First MCP tool get_ticker complete

Adds TickerDTO, domain-to-ToolError mapper, TickerService (L4),
get_ticker tool wired into FastMCP v3 lifespan with full production
bootstrap. End-to-end path: Client → MCP tool → TickerService →
Chain of Responsibility → Decorator chain → Provider → SupabaseGateway
cache-aside. Ready for M2.5 (second tool + Realtime + integration
tests).
```

```bash
cd /Users/laptop/dev/cryptozavr
git tag -a v0.0.7 -F /tmp/tag-msg.txt
rm /tmp/tag-msg.txt
git push origin main
git push origin v0.0.7
```

- [ ] **Step 5: Summary**

```bash
cd /Users/laptop/dev/cryptozavr
echo "=== M2.4 complete ==="
git log --oneline v0.0.6..HEAD
git tag -l | tail -5
```

---

## Acceptance Criteria

1. ✅ All 8 tasks done.
2. ✅ 17 new unit tests. Total ≥245 unit + 5 contract.
3. ✅ `get_ticker` surfaces cache-hit vs cache-miss via `reason_codes` in the DTO.
4. ✅ `SymbolNotFoundError` / `VenueNotSupportedError` / provider errors become readable `ToolError` messages — no stacktraces leak to clients.
5. ✅ `build_server(settings)` creates a server whose lifespan opens real Supabase + httpx + ccxt connections and closes them cleanly on shutdown.
6. ✅ Mypy strict + ruff + pytest green.
7. ✅ Tag `v0.0.7` pushed to github.com/evgenygurin/cryptozavr.

---

## Notes

- **`ctx.request_context.lifespan_context`** is the official FastMCP/MCP SDK way to read lifespan-scoped state inside a tool. The `AppState` dataclass is the payload yielded by the lifespan context manager.
- **Write-through is non-fatal** (from M2.3c): a Supabase outage won't block a fresh ticker from reaching the client. The DTO's `reason_codes` will contain `cache:write_failed` so the caller can tell.
- **Venue not supported** can mean two things: string doesn't match any `VenueId` member (e.g. `"binance"`), or the server just doesn't have a provider registered for a known venue. Both collapse into `VenueNotSupportedError` → same `ToolError` message. Good enough for MVP.
- **Symbol seed is tiny** (BTC-USDT, ETH-USDT on KuCoin). Extending the registry to a DB-driven flow is M2.5 scope. Callers requesting unseeded symbols hit `SymbolNotFoundError`.
- **SupabaseGateway/PgPoolConfig signatures** may require minor adaptation in Task 5 Step 2 — the plan's code is a shape, not a contract. The implementer should verify and adjust.
