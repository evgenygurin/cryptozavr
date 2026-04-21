# cryptozavr — Milestone 2.5: `get_ohlcv` tool + integration tests Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Добавить второй MCP tool `get_ohlcv(venue, symbol, timeframe, limit, since?, force_refresh)` через полный стек (mirror of `get_ticker`), плюс skip-safe integration tests против live Supabase для обоих tools.

**Architecture:** Симметричный OhlcvService рядом с TickerService — two services, shared chain/factory/gateway. AppState хранит обоих. `OHLCVSeriesDTO`/`OHLCVCandleDTO` Pydantic для wire-формата. Integration tests helpers проверяют full round-trip через реальную БД (skip если Supabase недоступен).

**Tech Stack:** Python 3.12, FastMCP 3.2.4, pydantic v2, asyncpg, supabase, pytest-asyncio. No new deps.

**Starting tag:** `v0.0.7`. Target: `v0.0.8`.

---

## File Structure

| Path | Responsibility |
|------|---------------|
| `src/cryptozavr/mcp/dtos.py` | MODIFY — add `OHLCVCandleDTO` + `OHLCVSeriesDTO` alongside existing `TickerDTO` |
| `src/cryptozavr/application/services/ohlcv_service.py` | NEW — `OhlcvService` + `OhlcvFetchResult` |
| `src/cryptozavr/mcp/tools/ohlcv.py` | NEW — `register_ohlcv_tool(mcp)` |
| `src/cryptozavr/mcp/bootstrap.py` | MODIFY — add `ohlcv_service` to `AppState`, construct it in `build_production_service` |
| `src/cryptozavr/mcp/server.py` | MODIFY — `register_ohlcv_tool(mcp)` |
| `tests/unit/mcp/test_dtos.py` | MODIFY — add 3 tests for OHLCV DTOs |
| `tests/unit/application/services/test_ohlcv_service.py` | NEW — 5 tests |
| `tests/unit/mcp/test_get_ohlcv_tool.py` | NEW — 3 Client(mcp) tests |
| `tests/integration/mcp/__init__.py` | NEW — empty |
| `tests/integration/mcp/test_tools_integration.py` | NEW — skip-safe integration for `get_ticker` + `get_ohlcv` |

---

## Tasks

### Task 1: OHLCV DTOs (OHLCVCandleDTO + OHLCVSeriesDTO)

**Files:**
- Modify: `src/cryptozavr/mcp/dtos.py`
- Modify: `tests/unit/mcp/test_dtos.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/unit/mcp/test_dtos.py`:
```python
from cryptozavr.domain.market_data import OHLCVCandle, OHLCVSeries
from cryptozavr.domain.value_objects import TimeRange, Timeframe
from cryptozavr.mcp.dtos import OHLCVCandleDTO, OHLCVSeriesDTO

@pytest.fixture
def btc_series() -> OHLCVSeries:
    symbol = SymbolRegistry().get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )
    candles = (
        OHLCVCandle(
            opened_at=Instant.from_ms(1_700_000_000_000),
            open=Decimal("100"),
            high=Decimal("110"),
            low=Decimal("95"),
            close=Decimal("105"),
            volume=Decimal("1000"),
        ),
        OHLCVCandle(
            opened_at=Instant.from_ms(1_700_000_060_000),
            open=Decimal("105"),
            high=Decimal("120"),
            low=Decimal("100"),
            close=Decimal("115"),
            volume=Decimal("2000"),
            closed=False,
        ),
    )
    return OHLCVSeries(
        symbol=symbol,
        timeframe=Timeframe.M1,
        candles=candles,
        range=TimeRange(
            start=Instant.from_ms(1_700_000_000_000),
            end=Instant.from_ms(1_700_000_120_000),
        ),
        quality=DataQuality(
            source=Provenance(venue_id="kucoin", endpoint="fetch_ohlcv"),
            fetched_at=Instant.from_ms(1_700_000_120_000),
            staleness=Staleness.FRESH,
            confidence=Confidence.HIGH,
            cache_hit=False,
        ),
    )

class TestOHLCVCandleDTO:
    def test_from_domain_copies_fields(self, btc_series: OHLCVSeries) -> None:
        dto = OHLCVCandleDTO.from_domain(btc_series.candles[0])
        assert dto.opened_at_ms == 1_700_000_000_000
        assert dto.open == Decimal("100")
        assert dto.high == Decimal("110")
        assert dto.low == Decimal("95")
        assert dto.close == Decimal("105")
        assert dto.volume == Decimal("1000")
        assert dto.closed is True

    def test_closed_false_flag_preserved(
        self, btc_series: OHLCVSeries,
    ) -> None:
        dto = OHLCVCandleDTO.from_domain(btc_series.candles[1])
        assert dto.closed is False

class TestOHLCVSeriesDTO:
    def test_from_domain_copies_fields(self, btc_series: OHLCVSeries) -> None:
        dto = OHLCVSeriesDTO.from_domain(
            btc_series, reason_codes=["venue:healthy", "cache:miss"],
        )
        assert dto.venue == "kucoin"
        assert dto.symbol == "BTC-USDT"
        assert dto.timeframe == "1m"
        assert dto.range_start_ms == 1_700_000_000_000
        assert dto.range_end_ms == 1_700_000_120_000
        assert len(dto.candles) == 2
        assert dto.candles[0].open == Decimal("100")
        assert dto.cache_hit is False
        assert dto.reason_codes == ["venue:healthy", "cache:miss"]

    def test_dto_serializes_to_json(self, btc_series: OHLCVSeries) -> None:
        dto = OHLCVSeriesDTO.from_domain(btc_series, reason_codes=[])
        payload = dto.model_dump(mode="json")
        assert payload["timeframe"] == "1m"
        assert len(payload["candles"]) == 2
        assert payload["candles"][0]["open"] == "100"
```

- [ ] **Step 2: Run — FAIL**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/mcp/test_dtos.py -v
```

- [ ] **Step 3: Implement**

Append to `src/cryptozavr/mcp/dtos.py` (at the bottom, after `TickerDTO`):
```python
from cryptozavr.domain.market_data import OHLCVCandle, OHLCVSeries

class OHLCVCandleDTO(BaseModel):
    """Wire-format single OHLCV bar."""

    model_config = ConfigDict(frozen=True)

    opened_at_ms: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    closed: bool

    @classmethod
    def from_domain(cls, candle: OHLCVCandle) -> OHLCVCandleDTO:
        return cls(
            opened_at_ms=candle.opened_at.to_ms(),
            open=candle.open,
            high=candle.high,
            low=candle.low,
            close=candle.close,
            volume=candle.volume,
            closed=candle.closed,
        )

class OHLCVSeriesDTO(BaseModel):
    """Wire-format OHLCV series for the get_ohlcv MCP tool."""

    model_config = ConfigDict(frozen=True)

    venue: str
    symbol: str
    timeframe: str
    range_start_ms: int
    range_end_ms: int
    candles: list[OHLCVCandleDTO]
    staleness: str
    confidence: str
    cache_hit: bool
    reason_codes: list[str]

    @classmethod
    def from_domain(
        cls, series: OHLCVSeries, reason_codes: list[str],
    ) -> OHLCVSeriesDTO:
        return cls(
            venue=series.symbol.venue.value,
            symbol=series.symbol.native_symbol,
            timeframe=series.timeframe.value,
            range_start_ms=series.range.start.to_ms(),
            range_end_ms=series.range.end.to_ms(),
            candles=[OHLCVCandleDTO.from_domain(c) for c in series.candles],
            staleness=series.quality.staleness.name.lower(),
            confidence=series.quality.confidence.name.lower(),
            cache_hit=series.quality.cache_hit,
            reason_codes=list(reason_codes),
        )
```

IMPORTANT: Move the new `OHLCVCandle`, `OHLCVSeries` import to the top imports block (don't keep mid-file). Ruff would flag E402 otherwise.

- [ ] **Step 4: PASS (old 3 tests + 5 new = 8 total in test_dtos.py).**

```bash
uv run pytest tests/unit/mcp/test_dtos.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src
```

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```text
feat(mcp): add OHLCV DTOs

OHLCVCandleDTO wraps a single bar with opened_at_ms, OHLC, volume,
closed flag. OHLCVSeriesDTO holds the full array plus venue/symbol/
timeframe/range metadata and the chain's reason_codes audit trail.
from_domain classmethod factories mirror TickerDTO.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/mcp/dtos.py tests/unit/mcp/test_dtos.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 2: `OhlcvService` L4 orchestrator

**Files:**
- Create: `src/cryptozavr/application/services/ohlcv_service.py`
- Create: `tests/unit/application/services/test_ohlcv_service.py`

- [ ] **Step 1: Write failing tests**

Write `tests/unit/application/services/test_ohlcv_service.py`:
```python
"""Test OhlcvService: venue/symbol validation + chain wiring."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from cryptozavr.application.services.ohlcv_service import (
    OhlcvFetchResult,
    OhlcvService,
)
from cryptozavr.domain.exceptions import (
    SymbolNotFoundError,
    VenueNotSupportedError,
)
from cryptozavr.domain.market_data import OHLCVCandle, OHLCVSeries
from cryptozavr.domain.quality import (
    Confidence,
    DataQuality,
    Provenance,
    Staleness,
)
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, TimeRange, Timeframe
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

def _make_series(symbol) -> OHLCVSeries:
    candle = OHLCVCandle(
        opened_at=Instant.from_ms(1_700_000_000_000),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("95"),
        close=Decimal("105"),
        volume=Decimal("1000"),
    )
    return OHLCVSeries(
        symbol=symbol,
        timeframe=Timeframe.M1,
        candles=(candle,),
        range=TimeRange(
            start=Instant.from_ms(1_700_000_000_000),
            end=Instant.from_ms(1_700_000_060_000),
        ),
        quality=DataQuality(
            source=Provenance(venue_id="kucoin", endpoint="fetch_ohlcv"),
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
def provider(registry: SymbolRegistry):
    symbol = registry.find(VenueId.KUCOIN, "BTC-USDT")
    assert symbol is not None
    p = MagicMock()
    p.fetch_ohlcv = AsyncMock(return_value=_make_series(symbol))
    return p

@pytest.fixture
def gateway():
    gw = MagicMock()
    gw.load_ohlcv = AsyncMock(return_value=None)
    gw.upsert_ohlcv = AsyncMock(return_value=1)
    return gw

@pytest.fixture
def service(registry, gateway, provider) -> OhlcvService:
    return OhlcvService(
        registry=registry,
        venue_states={VenueId.KUCOIN: VenueState(VenueId.KUCOIN)},
        providers={VenueId.KUCOIN: provider},
        gateway=gateway,
    )

class TestOhlcvService:
    @pytest.mark.asyncio
    async def test_fetch_ohlcv_returns_fetch_result(
        self, service: OhlcvService,
    ) -> None:
        result = await service.fetch_ohlcv(
            venue="kucoin", symbol="BTC-USDT",
            timeframe=Timeframe.M1, limit=100,
        )
        assert isinstance(result, OhlcvFetchResult)
        assert len(result.series.candles) == 1
        assert "provider:called" in result.reason_codes

    @pytest.mark.asyncio
    async def test_cache_hit_skips_provider(
        self, registry, gateway, provider,
    ) -> None:
        symbol = registry.find(VenueId.KUCOIN, "BTC-USDT")
        assert symbol is not None
        cached = _make_series(symbol)
        gateway.load_ohlcv = AsyncMock(return_value=cached)
        service = OhlcvService(
            registry=registry,
            venue_states={VenueId.KUCOIN: VenueState(VenueId.KUCOIN)},
            providers={VenueId.KUCOIN: provider},
            gateway=gateway,
        )
        result = await service.fetch_ohlcv(
            venue="kucoin", symbol="BTC-USDT",
            timeframe=Timeframe.M1, limit=100,
        )
        assert result.series is cached
        assert "cache:hit" in result.reason_codes
        provider.fetch_ohlcv.assert_not_called()

    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_cache(
        self, registry, gateway, provider,
    ) -> None:
        symbol = registry.find(VenueId.KUCOIN, "BTC-USDT")
        assert symbol is not None
        gateway.load_ohlcv = AsyncMock(return_value=_make_series(symbol))
        service = OhlcvService(
            registry=registry,
            venue_states={VenueId.KUCOIN: VenueState(VenueId.KUCOIN)},
            providers={VenueId.KUCOIN: provider},
            gateway=gateway,
        )
        result = await service.fetch_ohlcv(
            venue="kucoin", symbol="BTC-USDT",
            timeframe=Timeframe.M1, limit=100, force_refresh=True,
        )
        assert "cache:bypassed" in result.reason_codes
        provider.fetch_ohlcv.assert_awaited_once()
        gateway.load_ohlcv.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_venue_raises_venue_not_supported(
        self, service: OhlcvService,
    ) -> None:
        with pytest.raises(VenueNotSupportedError):
            await service.fetch_ohlcv(
                venue="binance", symbol="BTC-USDT",
                timeframe=Timeframe.M1, limit=100,
            )

    @pytest.mark.asyncio
    async def test_unknown_symbol_raises_symbol_not_found(
        self, service: OhlcvService,
    ) -> None:
        with pytest.raises(SymbolNotFoundError):
            await service.fetch_ohlcv(
                venue="kucoin", symbol="DOGE-USDT",
                timeframe=Timeframe.M1, limit=100,
            )
```

- [ ] **Step 2: FAIL**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/application/services/test_ohlcv_service.py -v
```

- [ ] **Step 3: Implement**

Write `src/cryptozavr/application/services/ohlcv_service.py`:
```python
"""OhlcvService: orchestrates chain + factory + gateway for OHLCV fetches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cryptozavr.domain.exceptions import (
    SymbolNotFoundError,
    VenueNotSupportedError,
)
from cryptozavr.domain.market_data import OHLCVSeries
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Timeframe
from cryptozavr.domain.venues import VenueId
from cryptozavr.infrastructure.providers.chain.assembly import (
    build_ohlcv_chain,
)
from cryptozavr.infrastructure.providers.chain.context import (
    FetchContext,
    FetchOperation,
    FetchRequest,
)
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

@dataclass(frozen=True, slots=True)
class OhlcvFetchResult:
    """OHLCV series + reason codes audit trail."""

    series: OHLCVSeries
    reason_codes: list[str]

class OhlcvService:
    """Facade: translates (venue, symbol, timeframe, limit) into a chain run."""

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

    async def fetch_ohlcv(
        self,
        *,
        venue: str,
        symbol: str,
        timeframe: Timeframe,
        limit: int = 500,
        since: Instant | None = None,
        force_refresh: bool = False,
    ) -> OhlcvFetchResult:
        venue_id = self._resolve_venue(venue)
        symbol_obj = self._registry.find(venue_id, symbol)
        if symbol_obj is None:
            raise SymbolNotFoundError(user_input=symbol, venue=venue)

        chain = build_ohlcv_chain(
            state=self._venue_states[venue_id],
            registry=self._registry,
            gateway=self._gateway,
            provider=self._providers[venue_id],
        )
        ctx = FetchContext(
            request=FetchRequest(
                operation=FetchOperation.OHLCV,
                symbol=symbol_obj,
                timeframe=timeframe,
                since=since,
                limit=limit,
                force_refresh=force_refresh,
            ),
        )
        result = await chain.handle(ctx)
        series: OHLCVSeries = result.metadata["result"]
        return OhlcvFetchResult(
            series=series,
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
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/application/services/test_ohlcv_service.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src
uv run pytest tests/unit -q 2>&1 | tail -3
```

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```bash
feat(app): add OhlcvService L4 orchestrator

Mirror of TickerService but for OHLCV. Validates venue/symbol, builds
the 5-handler chain per request with OHLCV operation + timeframe,
returns OhlcvFetchResult (series + reason codes). Unknown venue or
symbol surfaces as domain exception for MCP-layer translation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/application/services/ohlcv_service.py \
    tests/unit/application/services/test_ohlcv_service.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 3: `get_ohlcv` MCP tool + Client tests

**Files:**
- Create: `src/cryptozavr/mcp/tools/ohlcv.py`
- Create: `tests/unit/mcp/test_get_ohlcv_tool.py`

- [ ] **Step 1: Write failing tests**

Write `tests/unit/mcp/test_get_ohlcv_tool.py`:
```python
"""In-memory Client(mcp) tests for the get_ohlcv tool."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from cryptozavr.application.services.ohlcv_service import OhlcvFetchResult
from cryptozavr.domain.exceptions import SymbolNotFoundError
from cryptozavr.domain.market_data import OHLCVCandle, OHLCVSeries
from cryptozavr.domain.quality import (
    Confidence,
    DataQuality,
    Provenance,
    Staleness,
)
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, TimeRange, Timeframe
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.mcp.tools.ohlcv import register_ohlcv_tool

@dataclass(slots=True)
class _AppState:
    ohlcv_service: object

def _make_series() -> OHLCVSeries:
    symbol = SymbolRegistry().get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )
    candle = OHLCVCandle(
        opened_at=Instant.from_ms(1_700_000_000_000),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("95"),
        close=Decimal("105"),
        volume=Decimal("1000"),
    )
    return OHLCVSeries(
        symbol=symbol,
        timeframe=Timeframe.M1,
        candles=(candle,),
        range=TimeRange(
            start=Instant.from_ms(1_700_000_000_000),
            end=Instant.from_ms(1_700_000_060_000),
        ),
        quality=DataQuality(
            source=Provenance(venue_id="kucoin", endpoint="fetch_ohlcv"),
            fetched_at=Instant.from_ms(1_700_000_060_000),
            staleness=Staleness.FRESH,
            confidence=Confidence.HIGH,
            cache_hit=False,
        ),
    )

def _build_server(mock_service) -> FastMCP:
    @asynccontextmanager
    async def lifespan(server):
        yield _AppState(ohlcv_service=mock_service)

    mcp = FastMCP(name="test", version="0.0.0", lifespan=lifespan)
    register_ohlcv_tool(mcp)
    return mcp

@pytest.mark.asyncio
async def test_get_ohlcv_returns_dto_fields() -> None:
    service = MagicMock()
    service.fetch_ohlcv = AsyncMock(
        return_value=OhlcvFetchResult(
            series=_make_series(),
            reason_codes=["venue:healthy", "cache:miss", "provider:called"],
        ),
    )
    mcp = _build_server(service)
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_ohlcv",
            {
                "venue": "kucoin", "symbol": "BTC-USDT",
                "timeframe": "1m", "limit": 100,
            },
        )
    payload = result.structured_content
    assert payload["venue"] == "kucoin"
    assert payload["symbol"] == "BTC-USDT"
    assert payload["timeframe"] == "1m"
    assert len(payload["candles"]) == 1
    assert payload["reason_codes"] == [
        "venue:healthy", "cache:miss", "provider:called",
    ]
    service.fetch_ohlcv.assert_awaited_once()
    call_kwargs = service.fetch_ohlcv.call_args.kwargs
    assert call_kwargs["venue"] == "kucoin"
    assert call_kwargs["symbol"] == "BTC-USDT"
    assert call_kwargs["timeframe"] == Timeframe.M1
    assert call_kwargs["limit"] == 100
    assert call_kwargs["force_refresh"] is False

@pytest.mark.asyncio
async def test_get_ohlcv_forwards_force_refresh() -> None:
    service = MagicMock()
    service.fetch_ohlcv = AsyncMock(
        return_value=OhlcvFetchResult(
            series=_make_series(), reason_codes=["cache:bypassed"],
        ),
    )
    mcp = _build_server(service)
    async with Client(mcp) as client:
        await client.call_tool(
            "get_ohlcv",
            {
                "venue": "kucoin", "symbol": "BTC-USDT",
                "timeframe": "1m", "limit": 50, "force_refresh": True,
            },
        )
    call_kwargs = service.fetch_ohlcv.call_args.kwargs
    assert call_kwargs["force_refresh"] is True
    assert call_kwargs["limit"] == 50

@pytest.mark.asyncio
async def test_get_ohlcv_symbol_not_found_surfaces_tool_error() -> None:
    service = MagicMock()
    service.fetch_ohlcv = AsyncMock(
        side_effect=SymbolNotFoundError(user_input="DOGE-USDT", venue="kucoin"),
    )
    mcp = _build_server(service)
    async with Client(mcp) as client:
        with pytest.raises(ToolError) as exc_info:
            await client.call_tool(
                "get_ohlcv",
                {
                    "venue": "kucoin", "symbol": "DOGE-USDT",
                    "timeframe": "1m", "limit": 100,
                },
            )
    assert "DOGE-USDT" in str(exc_info.value)
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

Write `src/cryptozavr/mcp/tools/ohlcv.py`:
```python
"""get_ohlcv MCP tool registration."""

from __future__ import annotations

from typing import Annotated, Any, cast

from fastmcp import Context, FastMCP
from pydantic import Field

from cryptozavr.application.services.ohlcv_service import OhlcvService
from cryptozavr.domain.exceptions import DomainError, ValidationError
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.mcp.dtos import OHLCVSeriesDTO
from cryptozavr.mcp.errors import domain_to_tool_error

def register_ohlcv_tool(mcp: FastMCP) -> None:
    """Attach get_ohlcv tool to the given FastMCP instance."""

    @mcp.tool(
        name="get_ohlcv",
        description=(
            "Fetch OHLCV candles for a symbol on a venue at a given "
            "timeframe. Goes through the same 5-handler chain as "
            "get_ticker (venue-health → symbol-exists → staleness-bypass "
            "→ supabase-cache → provider-fetch). Set force_refresh=True "
            "to skip the cache."
        ),
        tags={"market", "public", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_ohlcv(
        venue: Annotated[
            str,
            Field(description="Venue id. Supported: kucoin, coingecko."),
        ],
        symbol: Annotated[
            str,
            Field(description="Native symbol, e.g. BTC-USDT (kucoin)."),
        ],
        timeframe: Annotated[
            str,
            Field(
                description=(
                    "Timeframe code: 1m, 5m, 15m, 1h, 4h, 1d. "
                    "Validated against Timeframe enum."
                ),
            ),
        ],
        ctx: Context,
        limit: Annotated[
            int,
            Field(ge=1, le=1000, description="Max candles to return (1..1000)."),
        ] = 500,
        force_refresh: Annotated[
            bool,
            Field(description="Bypass the Supabase cache."),
        ] = False,
    ) -> OHLCVSeriesDTO:
        try:
            tf = Timeframe(timeframe)
        except ValueError as exc:
            raise domain_to_tool_error(
                ValidationError(f"unknown timeframe: {timeframe!r}"),
            ) from exc
        service = cast(
            OhlcvService,
            cast(Any, ctx.lifespan_context).ohlcv_service,
        )
        try:
            result = await service.fetch_ohlcv(
                venue=venue,
                symbol=symbol,
                timeframe=tf,
                limit=limit,
                force_refresh=force_refresh,
            )
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc
        return OHLCVSeriesDTO.from_domain(result.series, result.reason_codes)
```

IMPORTANT: the tool validates the `timeframe` string into `Timeframe` enum and converts `ValueError` → `ValidationError` → `ToolError` before reaching the service. This keeps enum conversion as a pure MCP concern.

- [ ] **Step 4: PASS (3 tests).**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/mcp/test_get_ohlcv_tool.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src
```

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```bash
feat(mcp): add get_ohlcv tool

Second real MCP tool. Validates timeframe string into Timeframe enum
(unknown → ValidationError → ToolError), reads OhlcvService from
lifespan_context, catches DomainError, returns OHLCVSeriesDTO with
reason_codes. limit bounded 1..1000. Covered by in-memory Client(mcp)
tests (DTO mapping + force_refresh + error path).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/mcp/tools/ohlcv.py tests/unit/mcp/test_get_ohlcv_tool.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 4: Wire `ohlcv_service` into bootstrap + server

**Files:**
- Modify: `src/cryptozavr/mcp/bootstrap.py`
- Modify: `src/cryptozavr/mcp/server.py`

- [ ] **Step 1: Update bootstrap.py**

Modify `src/cryptozavr/mcp/bootstrap.py`:

1. Add import near the top alongside `TickerService`:
```python
from cryptozavr.application.services.ohlcv_service import OhlcvService
from cryptozavr.application.services.ticker_service import TickerService
```

2. Update `AppState` dataclass to include `ohlcv_service`:
```python
@dataclass(slots=True)
class AppState:
    """Lifespan-scoped application state exposed to tools."""

    ticker_service: TickerService
    ohlcv_service: OhlcvService
```

3. Update `build_production_service` return type:
```python
async def build_production_service(
    settings: Settings,
) -> tuple[TickerService, OhlcvService, Callable[[], Awaitable[None]]]:
```

4. At the end of `build_production_service`, after `ticker_service = TickerService(...)`, add:
```python
    ohlcv_service = OhlcvService(
        registry=registry,
        venue_states=venue_states,
        providers=providers,
        gateway=gateway,
    )
```

5. Update the final return:
```python
    return ticker_service, ohlcv_service, cleanup
```

IMPORTANT: Rename the existing `service` local in bootstrap to `ticker_service` (if it was named `service`) for clarity. Confirm by reading the current file first:
```bash
cat src/cryptozavr/mcp/bootstrap.py
```

- [ ] **Step 2: Update server.py**

Modify `src/cryptozavr/mcp/server.py`:

1. Add import:
```python
from cryptozavr.mcp.tools.ohlcv import register_ohlcv_tool
from cryptozavr.mcp.tools.ticker import register_ticker_tool
```

2. Update the lifespan to unpack three values:
```python
    @asynccontextmanager
    async def lifespan(
        _server: FastMCP[AppState],
    ) -> AsyncIterator[AppState]:
        ticker_service, ohlcv_service, cleanup = (
            await build_production_service(settings)
        )
        _LOGGER.info(
            "cryptozavr-research started",
            extra={"mode": settings.mode.value, "version": __version__},
        )
        try:
            yield AppState(
                ticker_service=ticker_service,
                ohlcv_service=ohlcv_service,
            )
        finally:
            await cleanup()
```

3. Register ohlcv tool next to ticker:
```python
    _register_echo(mcp)
    register_ticker_tool(mcp)
    register_ohlcv_tool(mcp)
    return mcp
```

- [ ] **Step 3: Smoke checks**

```bash
cd /Users/laptop/dev/cryptozavr
uv run ruff check . && uv run ruff format --check . && uv run mypy src
uv run pytest tests/unit tests/contract -m "not integration" -q 2>&1 | tail -3
```

Expected: all clean; ≥265 tests.

- [ ] **Step 4: Commit**

Write to /tmp/commit-msg.txt:
```text
feat(mcp): wire ohlcv_service into AppState + register get_ohlcv

Bootstrap now produces both TickerService and OhlcvService (sharing the
same registries, providers, and gateway). AppState carries both. The
server lifespan unpacks the triple and registers both tools.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/mcp/bootstrap.py src/cryptozavr/mcp/server.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 5: Integration tests against live Supabase (skip-safe)

**Files:**
- Create: `tests/integration/mcp/__init__.py` (empty)
- Create: `tests/integration/mcp/test_tools_integration.py`

- [ ] **Step 1: Inspect existing integration conftest + markers**

```bash
cd /Users/laptop/dev/cryptozavr
cat tests/integration/conftest.py
grep -n "integration" pyproject.toml
```

Take note of the `@pytest.mark.integration` marker and the skip-logic pattern (how existing tests detect a running Supabase).

- [ ] **Step 2: Write the integration tests**

Write empty `tests/integration/mcp/__init__.py`.

Write `tests/integration/mcp/test_tools_integration.py`:
```python
"""End-to-end integration tests for the get_ticker / get_ohlcv MCP tools.

Skip-safe: requires a running local Supabase with migrations applied.
Uses the live FastMCP lifespan + real httpx/ccxt providers.
"""

from __future__ import annotations

import pytest
from fastmcp import Client

from cryptozavr.mcp.server import build_server
from cryptozavr.mcp.settings import Settings

pytestmark = pytest.mark.integration

@pytest.fixture
def settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

@pytest.mark.asyncio
async def test_get_ticker_full_stack_against_live_supabase(
    settings: Settings,
) -> None:
    mcp = build_server(settings)
    async with Client(mcp) as client:
        # First call — should miss cache and hit the provider.
        first = await client.call_tool(
            "get_ticker", {"venue": "kucoin", "symbol": "BTC-USDT"},
        )
        assert first.structured_content["venue"] == "kucoin"
        assert first.structured_content["symbol"] == "BTC-USDT"
        assert "provider:called" in first.structured_content["reason_codes"]

        # Second call within TTL — may or may not hit cache depending on
        # in-memory decorator TTL; we only assert it returns a ticker.
        second = await client.call_tool(
            "get_ticker", {"venue": "kucoin", "symbol": "BTC-USDT"},
        )
        assert second.structured_content["symbol"] == "BTC-USDT"

@pytest.mark.asyncio
async def test_get_ohlcv_full_stack_against_live_supabase(
    settings: Settings,
) -> None:
    mcp = build_server(settings)
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_ohlcv",
            {
                "venue": "kucoin", "symbol": "BTC-USDT",
                "timeframe": "1m", "limit": 10,
            },
        )
    payload = result.structured_content
    assert payload["venue"] == "kucoin"
    assert payload["symbol"] == "BTC-USDT"
    assert payload["timeframe"] == "1m"
    assert len(payload["candles"]) >= 1
    assert "provider:called" in payload["reason_codes"]
```

IMPORTANT: the existing `tests/integration/conftest.py` handles the "Supabase not available → skip" logic via the `@pytest.mark.integration` marker + a fixture that pings the DB. Reuse it — don't duplicate skip logic. If `conftest.py` doesn't already expose the skip mechanism, fall back to:
```python
pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

@pytest.fixture(autouse=True)
def _skip_if_no_supabase():
    import os
    if not os.getenv("SUPABASE_DB_URL"):
        pytest.skip("SUPABASE_DB_URL not set")
```

- [ ] **Step 3: Run**

```bash
cd /Users/laptop/dev/cryptozavr
# With Supabase not running — tests should be collected then skipped:
uv run pytest tests/integration/mcp -v 2>&1 | tail -10
# Expected: tests skipped or errored with clear "no supabase" reason, not true failures
```

If tests ERROR (not SKIP) when Supabase isn't available, adjust the skip fixture. We don't want CI to fail when Supabase isn't up.

- [ ] **Step 4: Full suite**

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src
uv run pytest tests/unit tests/contract -m "not integration" -q 2>&1 | tail -3
```

No regression in unit/contract suite.

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```text
test(integration): add end-to-end MCP tool tests

get_ticker and get_ohlcv round-trip through the full production stack
(FastMCP lifespan → TickerService/OhlcvService → chain → factory →
real KuCoin provider → live Supabase cache-aside). Marked integration
and skipped when SUPABASE_DB_URL is absent, so CI stays green.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add tests/integration/mcp/__init__.py tests/integration/mcp/test_tools_integration.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 6: CHANGELOG + tag v0.0.8 + push

- [ ] **Step 1: Verify**

```bash
cd /Users/laptop/dev/cryptozavr
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest tests/unit tests/contract -m "not integration" -v 2>&1 | tail -10
```

Expected: all clean; ≥265 unit + 5 contract tests.

- [ ] **Step 2: Update CHANGELOG**

Edit `/Users/laptop/dev/cryptozavr/CHANGELOG.md`. Find:
```markdown
## [Unreleased]

## [0.0.7] - 2026-04-21
```

Replace with:
```markdown
## [Unreleased]

## [0.0.8] - 2026-04-21

### Added — M2.5 `get_ohlcv` tool + integration tests
- `OHLCVCandleDTO` / `OHLCVSeriesDTO` (Pydantic): wire formats for OHLCV data. Candle has opened_at_ms + OHLC + volume + closed; series has venue/symbol/timeframe/range/candles + reason_codes.
- `OhlcvService` (L4 Application): mirror of `TickerService` — validates venue/symbol, builds the `build_ohlcv_chain` per request with `FetchOperation.OHLCV`, returns `OhlcvFetchResult` (series + reason codes).
- `register_ohlcv_tool(mcp)`: `get_ohlcv(venue, symbol, timeframe, limit, force_refresh)` validates timeframe string → `Timeframe` enum, reads `OhlcvService` from lifespan_context, catches `DomainError`, returns `OHLCVSeriesDTO`. `limit` bounded 1..1000.
- `AppState` now carries both `ticker_service` and `ohlcv_service`. `build_production_service` returns a triple `(ticker_service, ohlcv_service, cleanup)`.
- Integration tests: `tests/integration/mcp/test_tools_integration.py` runs `get_ticker` and `get_ohlcv` through the real FastMCP lifespan against live Supabase + KuCoin. Marked `@pytest.mark.integration`; auto-skip when `SUPABASE_DB_URL` is absent.
- ~13 new unit tests (OHLCV DTOs 5 + OhlcvService 5 + get_ohlcv tool 3) + 2 integration tests (skip-safe).

### Next
- M2.6: `get_order_book`, `get_trades` (non-cached); refine Realtime stub (phase 1.5 prep).

## [0.0.7] - 2026-04-21
```

- [ ] **Step 3: Commit CHANGELOG + plan**

```bash
cd /Users/laptop/dev/cryptozavr
git add CHANGELOG.md
git add docs/superpowers/plans/2026-04-21-cryptozavr-m2.5-get-ohlcv-and-integration.md 2>/dev/null || true
```

Write to /tmp/commit-msg.txt:
```bash
docs: finalize CHANGELOG for v0.0.8 (M2.5 get_ohlcv + integration)

Second MCP tool through the full stack plus end-to-end integration
tests against live Supabase (skip-safe).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

- [ ] **Step 4: Tag + push**

Write tag message to /tmp/tag-msg.txt:
```bash
M2.5 get_ohlcv + integration tests complete

Second real MCP tool (OHLCV candles via 5-handler chain), OhlcvService
L4 orchestrator, end-to-end integration tests for both tools against
live Supabase (skip-safe). AppState carries both services. Ready for
M2.6 (order_book + trades).
```

```bash
cd /Users/laptop/dev/cryptozavr
git tag -a v0.0.8 -F /tmp/tag-msg.txt
rm /tmp/tag-msg.txt
git push origin main
git push origin v0.0.8
```

- [ ] **Step 5: Summary**

```bash
cd /Users/laptop/dev/cryptozavr
echo "=== M2.5 complete ==="
git log --oneline v0.0.7..HEAD
git tag -l | tail -5
```

---

## Acceptance Criteria

1. ✅ All 6 tasks done.
2. ✅ ≥13 new unit tests + 2 integration tests (skip-safe). Total ≥265 unit + 5 contract.
3. ✅ `get_ohlcv` returns `OHLCVSeriesDTO` with `candles` array + `reason_codes`.
4. ✅ Unknown `timeframe` string surfaces as `ToolError` ("Invalid input: unknown timeframe: ...").
5. ✅ Integration tests collected but skipped when `SUPABASE_DB_URL` is absent (CI stays green).
6. ✅ Mypy strict + ruff + pytest green.
7. ✅ Tag `v0.0.8` pushed to github.com/evgenygurin/cryptozavr.

---

## Notes

- **Timeframe validation lives in the MCP tool**, not in `OhlcvService`. The tool converts string → enum and raises `ValidationError` on unknown values. Service assumes the enum is already valid. This keeps Application-layer signatures type-safe (`timeframe: Timeframe`, not `str`).
- **AppState shape change is a breaking internal API**, but no external consumers depend on it yet — both M2.4 and M2.5 test lifespans are local. Task 4 updates the two call sites (bootstrap.py + server.py) atomically.
- **Integration tests may be slow** (real KuCoin + real Supabase). They're gated behind `@pytest.mark.integration` so the default `pytest` invocation (no `-m integration`) skips them entirely.
- **Realtime stub stays as-is** for M2.5. Phase 1.5 (real postgres_changes subscriptions) was never part of this milestone.
- **No DTO unification yet**: `TickerDTO` and `OHLCVSeriesDTO` are siblings. If a shared base emerges naturally in M2.6 (order_book/trades), factor then. YAGNI.
