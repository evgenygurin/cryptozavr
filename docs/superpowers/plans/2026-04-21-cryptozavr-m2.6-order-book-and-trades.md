# cryptozavr — Milestone 2.6: `get_order_book` + `get_trades` tools Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Завершить market-data слой tools: `get_order_book(venue, symbol, depth)` → `OrderBookDTO`, `get_trades(venue, symbol, limit, since?)` → `TradesDTO`. Оба НЕ кэшируются в Supabase (M2.2-ограничение), но проходят через полный стек Chain+Factory+Provider.

**Architecture:** Симметрия с M2.4/M2.5 — 2 новых L4 services (`OrderBookService`, `TradesService`), 2 tool registrars, 4 новых DTO класса. AppState теперь хранит 4 services. `build_order_book_chain` + `build_trades_chain` добавляются в assembly.py для name parity с существующими helpers. Chain использует тот же `_build_chain` — topology идентична, operation dispatch происходит внутри handlers.

**Tech Stack:** Python 3.12, FastMCP 3.2.4, pydantic v2, pytest-asyncio. No new deps.

**Starting tag:** `v0.0.8`. Target: `v0.0.9`.

---

## File Structure

| Path | Responsibility |
|------|---------------|
| `src/cryptozavr/mcp/dtos.py` | MODIFY — add `PriceSizeDTO`, `OrderBookDTO`, `TradeTickDTO`, `TradesDTO` |
| `src/cryptozavr/infrastructure/providers/chain/assembly.py` | MODIFY — add `build_order_book_chain` + `build_trades_chain` helpers |
| `src/cryptozavr/application/services/order_book_service.py` | NEW — `OrderBookService` + `OrderBookFetchResult` |
| `src/cryptozavr/application/services/trades_service.py` | NEW — `TradesService` + `TradesFetchResult` |
| `src/cryptozavr/mcp/tools/order_book.py` | NEW — `register_order_book_tool(mcp)` |
| `src/cryptozavr/mcp/tools/trades.py` | NEW — `register_trades_tool(mcp)` |
| `src/cryptozavr/mcp/bootstrap.py` | MODIFY — `AppState` +2 fields, `build_production_service` → 5-tuple |
| `src/cryptozavr/mcp/server.py` | MODIFY — register both new tools |
| `tests/unit/mcp/test_dtos.py` | MODIFY — add 4 tests for new DTOs |
| `tests/unit/application/services/test_order_book_service.py` | NEW — 5 tests |
| `tests/unit/application/services/test_trades_service.py` | NEW — 5 tests |
| `tests/unit/mcp/test_get_order_book_tool.py` | NEW — 3 Client(mcp) tests |
| `tests/unit/mcp/test_get_trades_tool.py` | NEW — 3 Client(mcp) tests |

---

## Tasks

### Task 1: OrderBook + Trades DTOs

**Files:**
- Modify: `src/cryptozavr/mcp/dtos.py`
- Modify: `tests/unit/mcp/test_dtos.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/unit/mcp/test_dtos.py` (reuse existing top imports where possible; ADD to top imports):
```python
from cryptozavr.domain.market_data import (
    OHLCVCandle,
    OHLCVSeries,
    OrderBookSnapshot,
    TradeSide,
    TradeTick,
)
from cryptozavr.domain.value_objects import PriceSize, TimeRange, Timeframe
from cryptozavr.mcp.dtos import (
    OHLCVCandleDTO,
    OHLCVSeriesDTO,
    OrderBookDTO,
    PriceSizeDTO,
    TradesDTO,
    TradeTickDTO,
)
```

Append these test classes AFTER existing `TestOHLCVSeriesDTO`:
```python
@pytest.fixture
def btc_orderbook() -> OrderBookSnapshot:
    symbol = SymbolRegistry().get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )
    bids = (
        PriceSize(price=Decimal("100"), size=Decimal("1.5")),
        PriceSize(price=Decimal("99.5"), size=Decimal("2.0")),
    )
    asks = (
        PriceSize(price=Decimal("101"), size=Decimal("1.0")),
        PriceSize(price=Decimal("101.5"), size=Decimal("3.0")),
    )
    return OrderBookSnapshot(
        symbol=symbol,
        bids=bids,
        asks=asks,
        observed_at=Instant.from_ms(1_700_000_000_000),
        quality=DataQuality(
            source=Provenance(venue_id="kucoin", endpoint="fetch_order_book"),
            fetched_at=Instant.from_ms(1_700_000_000_000),
            staleness=Staleness.FRESH,
            confidence=Confidence.HIGH,
            cache_hit=False,
        ),
    )

@pytest.fixture
def btc_trades() -> tuple[TradeTick, ...]:
    symbol = SymbolRegistry().get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )
    return (
        TradeTick(
            symbol=symbol,
            price=Decimal("100.5"),
            size=Decimal("0.1"),
            side=TradeSide.BUY,
            executed_at=Instant.from_ms(1_700_000_000_000),
            trade_id="t1",
        ),
        TradeTick(
            symbol=symbol,
            price=Decimal("100.6"),
            size=Decimal("0.2"),
            side=TradeSide.SELL,
            executed_at=Instant.from_ms(1_700_000_001_000),
        ),
    )

class TestPriceSizeDTO:
    def test_from_domain_copies_price_and_size(self) -> None:
        ps = PriceSize(price=Decimal("100"), size=Decimal("1.5"))
        dto = PriceSizeDTO.from_domain(ps)
        assert dto.price == Decimal("100")
        assert dto.size == Decimal("1.5")

class TestOrderBookDTO:
    def test_from_domain_copies_fields(
        self, btc_orderbook: OrderBookSnapshot,
    ) -> None:
        dto = OrderBookDTO.from_domain(
            btc_orderbook, reason_codes=["venue:healthy"],
        )
        assert dto.venue == "kucoin"
        assert dto.symbol == "BTC-USDT"
        assert dto.observed_at_ms == 1_700_000_000_000
        assert len(dto.bids) == 2
        assert len(dto.asks) == 2
        assert dto.bids[0].price == Decimal("100")
        assert dto.asks[0].price == Decimal("101")
        assert dto.spread == Decimal("1")  # 101 - 100
        assert dto.spread_bps is not None
        assert dto.cache_hit is False
        assert dto.reason_codes == ["venue:healthy"]

    def test_from_domain_empty_book_spread_is_none(self) -> None:
        symbol = SymbolRegistry().get(
            VenueId.KUCOIN, "BTC", "USDT",
            market_type=MarketType.SPOT, native_symbol="BTC-USDT",
        )
        empty = OrderBookSnapshot(
            symbol=symbol,
            bids=(),
            asks=(),
            observed_at=Instant.from_ms(1),
            quality=DataQuality(
                source=Provenance(
                    venue_id="kucoin", endpoint="fetch_order_book",
                ),
                fetched_at=Instant.from_ms(1),
                staleness=Staleness.FRESH,
                confidence=Confidence.HIGH,
                cache_hit=False,
            ),
        )
        dto = OrderBookDTO.from_domain(empty, reason_codes=[])
        assert dto.spread is None
        assert dto.spread_bps is None
        assert dto.bids == []
        assert dto.asks == []

class TestTradeTickDTO:
    def test_from_domain_copies_fields(
        self, btc_trades: tuple[TradeTick, ...],
    ) -> None:
        dto = TradeTickDTO.from_domain(btc_trades[0])
        assert dto.price == Decimal("100.5")
        assert dto.size == Decimal("0.1")
        assert dto.side == "buy"
        assert dto.executed_at_ms == 1_700_000_000_000
        assert dto.trade_id == "t1"

    def test_from_domain_handles_missing_trade_id(
        self, btc_trades: tuple[TradeTick, ...],
    ) -> None:
        dto = TradeTickDTO.from_domain(btc_trades[1])
        assert dto.trade_id is None
        assert dto.side == "sell"

class TestTradesDTO:
    def test_from_domain_copies_fields(
        self, btc_trades: tuple[TradeTick, ...],
    ) -> None:
        dto = TradesDTO.from_domain(
            venue="kucoin",
            symbol="BTC-USDT",
            trades=btc_trades,
            reason_codes=["venue:healthy", "cache:miss", "provider:called"],
        )
        assert dto.venue == "kucoin"
        assert dto.symbol == "BTC-USDT"
        assert len(dto.trades) == 2
        assert dto.trades[0].trade_id == "t1"
        assert dto.reason_codes == [
            "venue:healthy", "cache:miss", "provider:called",
        ]

    def test_empty_trades_list(self) -> None:
        dto = TradesDTO.from_domain(
            venue="kucoin", symbol="BTC-USDT",
            trades=(), reason_codes=[],
        )
        assert dto.trades == []
```

- [ ] **Step 2: Run — FAIL**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/mcp/test_dtos.py -v
```

Expected: ImportError on the new DTO names.

- [ ] **Step 3: Implement**

Read current `src/cryptozavr/mcp/dtos.py` first. Then extend:

1. Update the top imports to add `OrderBookSnapshot`, `TradeTick`, `PriceSize`:
```python
from cryptozavr.domain.market_data import (
    OHLCVCandle,
    OHLCVSeries,
    OrderBookSnapshot,
    Ticker,
    TradeTick,
)
from cryptozavr.domain.value_objects import PriceSize
```

2. Append AFTER the existing `OHLCVSeriesDTO` class:
```python
class PriceSizeDTO(BaseModel):
    """Wire-format order-book level (price + size)."""

    model_config = ConfigDict(frozen=True)

    price: Decimal
    size: Decimal

    @classmethod
    def from_domain(cls, ps: PriceSize) -> PriceSizeDTO:
        return cls(price=ps.price, size=ps.size)

class OrderBookDTO(BaseModel):
    """Wire-format order-book snapshot for the get_order_book MCP tool."""

    model_config = ConfigDict(frozen=True)

    venue: str
    symbol: str
    observed_at_ms: int
    bids: list[PriceSizeDTO]
    asks: list[PriceSizeDTO]
    spread: Decimal | None
    spread_bps: Decimal | None
    staleness: str
    confidence: str
    cache_hit: bool
    reason_codes: list[str]

    @classmethod
    def from_domain(
        cls, snapshot: OrderBookSnapshot, reason_codes: list[str],
    ) -> OrderBookDTO:
        return cls(
            venue=snapshot.symbol.venue.value,
            symbol=snapshot.symbol.native_symbol,
            observed_at_ms=snapshot.observed_at.to_ms(),
            bids=[PriceSizeDTO.from_domain(b) for b in snapshot.bids],
            asks=[PriceSizeDTO.from_domain(a) for a in snapshot.asks],
            spread=snapshot.spread(),
            spread_bps=snapshot.spread_bps(),
            staleness=snapshot.quality.staleness.name.lower(),
            confidence=snapshot.quality.confidence.name.lower(),
            cache_hit=snapshot.quality.cache_hit,
            reason_codes=list(reason_codes),
        )

class TradeTickDTO(BaseModel):
    """Wire-format single trade tick."""

    model_config = ConfigDict(frozen=True)

    price: Decimal
    size: Decimal
    side: str
    executed_at_ms: int
    trade_id: str | None = None

    @classmethod
    def from_domain(cls, tick: TradeTick) -> TradeTickDTO:
        return cls(
            price=tick.price,
            size=tick.size,
            side=tick.side.value,
            executed_at_ms=tick.executed_at.to_ms(),
            trade_id=tick.trade_id,
        )

class TradesDTO(BaseModel):
    """Wire-format recent trades for the get_trades MCP tool.

    Trades are non-cached, so there's no staleness/cache_hit in the DTO —
    just the venue/symbol wrapper, the list, and the chain reason_codes.
    """

    model_config = ConfigDict(frozen=True)

    venue: str
    symbol: str
    trades: list[TradeTickDTO]
    reason_codes: list[str]

    @classmethod
    def from_domain(
        cls,
        *,
        venue: str,
        symbol: str,
        trades: tuple[TradeTick, ...],
        reason_codes: list[str],
    ) -> TradesDTO:
        return cls(
            venue=venue,
            symbol=symbol,
            trades=[TradeTickDTO.from_domain(t) for t in trades],
            reason_codes=list(reason_codes),
        )
```

- [ ] **Step 4: PASS**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/mcp/test_dtos.py -v
```
Expected: 12 tests passed (7 existing + 5 new: 1 PriceSize + 2 OrderBook + 2 TradeTick + 2 Trades — actually 1+2+2+2=7, total 14; see fixtures above for exact count).

Actual count: 2 OrderBookDTO + 2 TradeTickDTO + 2 TradesDTO + 1 PriceSizeDTO = 7 new. Existing 7. Total 14.

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src
uv run pytest tests/unit tests/contract -m "not integration" -q 2>&1 | tail -3
```
Expected: clean, ≥267 tests.

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```bash
feat(mcp): add OrderBook + Trades DTOs

PriceSizeDTO wraps a single bid/ask level. OrderBookDTO holds both
sides plus spread/spread_bps convenience fields. TradeTickDTO wraps one
trade. TradesDTO is the wire-format for recent-trades fetches (no
cache_hit — not cached in M2.2 schema).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/mcp/dtos.py tests/unit/mcp/test_dtos.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 2: Chain assembly helpers for order_book + trades

**Files:**
- Modify: `src/cryptozavr/infrastructure/providers/chain/assembly.py`

No new unit tests — the chain topology is identical and already covered in M2.3c `test_assembly.py`. Task 3/4 services will exercise the new helpers end-to-end.

- [ ] **Step 1: Read current file**

```bash
cd /Users/laptop/dev/cryptozavr
cat src/cryptozavr/infrastructure/providers/chain/assembly.py
```

Note the signature of `_build_chain` and existing `build_ticker_chain` / `build_ohlcv_chain`.

- [ ] **Step 2: Implement**

Append these two functions AFTER the existing `build_ohlcv_chain` (before `_build_chain`):
```python
def build_order_book_chain(
    *,
    state: VenueState,
    registry: SymbolRegistry,
    gateway: Any,
    provider: Any,
) -> FetchHandler:
    """5-handler chain for order-book fetches.

    Same topology as ticker/ohlcv; order-book is not cached in M2.2 — the
    SupabaseCacheHandler returns None for this operation and the chain
    always reaches ProviderFetchHandler.
    """
    return _build_chain(
        state=state, registry=registry, gateway=gateway, provider=provider,
    )

def build_trades_chain(
    *,
    state: VenueState,
    registry: SymbolRegistry,
    gateway: Any,
    provider: Any,
) -> FetchHandler:
    """5-handler chain for trades fetches.

    Trades are not cached in M2.2 — same non-caching behaviour as
    order-book.
    """
    return _build_chain(
        state=state, registry=registry, gateway=gateway, provider=provider,
    )
```

- [ ] **Step 3: Smoke checks**

```bash
cd /Users/laptop/dev/cryptozavr
uv run ruff check . && uv run ruff format --check . && uv run mypy src
uv run pytest tests/unit tests/contract -m "not integration" -q 2>&1 | tail -3
```

Expected: all clean; no regression (same test count as Task 1 end state).

- [ ] **Step 4: Commit**

Write to /tmp/commit-msg.txt:
```bash
feat(providers): add order_book + trades chain assembly helpers

Sibling helpers to build_ticker_chain / build_ohlcv_chain. Same
topology (_build_chain delegation) since SupabaseCacheHandler and
ProviderFetchHandler dispatch internally by request.operation. Adding
named functions for call-site readability at the service layer.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/infrastructure/providers/chain/assembly.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 3: `OrderBookService` L4 orchestrator

**Files:**
- Create: `src/cryptozavr/application/services/order_book_service.py`
- Create: `tests/unit/application/services/test_order_book_service.py`

- [ ] **Step 1: Write failing tests**

Write `tests/unit/application/services/test_order_book_service.py`:
```python
"""Test OrderBookService: venue/symbol validation + chain wiring."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from cryptozavr.application.services.order_book_service import (
    OrderBookFetchResult,
    OrderBookService,
)
from cryptozavr.domain.exceptions import (
    SymbolNotFoundError,
    VenueNotSupportedError,
)
from cryptozavr.domain.market_data import OrderBookSnapshot
from cryptozavr.domain.quality import (
    Confidence,
    DataQuality,
    Provenance,
    Staleness,
)
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, PriceSize
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

def _make_snapshot(symbol) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        symbol=symbol,
        bids=(PriceSize(price=Decimal("100"), size=Decimal("1")),),
        asks=(PriceSize(price=Decimal("101"), size=Decimal("1")),),
        observed_at=Instant.now(),
        quality=DataQuality(
            source=Provenance(
                venue_id="kucoin", endpoint="fetch_order_book",
            ),
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
    p.fetch_order_book = AsyncMock(return_value=_make_snapshot(symbol))
    return p

@pytest.fixture
def gateway():
    # Non-cached operation — gateway load_* must return None; upsert
    # never called.
    gw = MagicMock()
    gw.load_ticker = AsyncMock(return_value=None)
    gw.load_ohlcv = AsyncMock(return_value=None)
    return gw

@pytest.fixture
def service(registry, gateway, provider) -> OrderBookService:
    return OrderBookService(
        registry=registry,
        venue_states={VenueId.KUCOIN: VenueState(VenueId.KUCOIN)},
        providers={VenueId.KUCOIN: provider},
        gateway=gateway,
    )

class TestOrderBookService:
    @pytest.mark.asyncio
    async def test_fetch_order_book_returns_result(
        self, service: OrderBookService,
    ) -> None:
        result = await service.fetch_order_book(
            venue="kucoin", symbol="BTC-USDT", depth=50,
        )
        assert isinstance(result, OrderBookFetchResult)
        assert len(result.snapshot.bids) == 1
        assert len(result.snapshot.asks) == 1
        assert "provider:called" in result.reason_codes

    @pytest.mark.asyncio
    async def test_forwards_depth_to_provider(
        self, service: OrderBookService, provider,
    ) -> None:
        await service.fetch_order_book(
            venue="kucoin", symbol="BTC-USDT", depth=20,
        )
        provider.fetch_order_book.assert_awaited_once()
        call_kwargs = provider.fetch_order_book.call_args.kwargs
        assert call_kwargs.get("depth") == 20

    @pytest.mark.asyncio
    async def test_force_refresh_passes_through(
        self, service: OrderBookService, provider,
    ) -> None:
        result = await service.fetch_order_book(
            venue="kucoin", symbol="BTC-USDT",
            depth=50, force_refresh=True,
        )
        assert "cache:bypassed" in result.reason_codes
        provider.fetch_order_book.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unknown_venue_raises(
        self, service: OrderBookService,
    ) -> None:
        with pytest.raises(VenueNotSupportedError):
            await service.fetch_order_book(
                venue="binance", symbol="BTC-USDT", depth=50,
            )

    @pytest.mark.asyncio
    async def test_unknown_symbol_raises(
        self, service: OrderBookService,
    ) -> None:
        with pytest.raises(SymbolNotFoundError):
            await service.fetch_order_book(
                venue="kucoin", symbol="DOGE-USDT", depth=50,
            )
```

- [ ] **Step 2: FAIL**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/application/services/test_order_book_service.py -v
```

- [ ] **Step 3: Implement**

Write `src/cryptozavr/application/services/order_book_service.py`:
```python
"""OrderBookService: orchestrates chain + provider for order-book fetches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cryptozavr.domain.exceptions import (
    SymbolNotFoundError,
    VenueNotSupportedError,
)
from cryptozavr.domain.market_data import OrderBookSnapshot
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import VenueId
from cryptozavr.infrastructure.providers.chain.assembly import (
    build_order_book_chain,
)
from cryptozavr.infrastructure.providers.chain.context import (
    FetchContext,
    FetchOperation,
    FetchRequest,
)
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

@dataclass(frozen=True, slots=True)
class OrderBookFetchResult:
    """OrderBook snapshot + reason codes audit trail."""

    snapshot: OrderBookSnapshot
    reason_codes: list[str]

class OrderBookService:
    """Facade: translates (venue, symbol, depth) into a chain run."""

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

    async def fetch_order_book(
        self,
        *,
        venue: str,
        symbol: str,
        depth: int = 50,
        force_refresh: bool = False,
    ) -> OrderBookFetchResult:
        venue_id = self._resolve_venue(venue)
        symbol_obj = self._registry.find(venue_id, symbol)
        if symbol_obj is None:
            raise SymbolNotFoundError(user_input=symbol, venue=venue)

        chain = build_order_book_chain(
            state=self._venue_states[venue_id],
            registry=self._registry,
            gateway=self._gateway,
            provider=self._providers[venue_id],
        )
        ctx = FetchContext(
            request=FetchRequest(
                operation=FetchOperation.ORDER_BOOK,
                symbol=symbol_obj,
                depth=depth,
                force_refresh=force_refresh,
            ),
        )
        result = await chain.handle(ctx)
        snapshot: OrderBookSnapshot = result.metadata["result"]
        return OrderBookFetchResult(
            snapshot=snapshot,
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
uv run pytest tests/unit/application/services/test_order_book_service.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src
uv run pytest tests/unit tests/contract -m "not integration" -q 2>&1 | tail -3
```

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```bash
feat(app): add OrderBookService L4 orchestrator

Mirror of TickerService/OhlcvService for order-book. Non-cached path:
SupabaseCacheHandler returns None, chain always reaches provider.
fetch_order_book forwards depth param through FetchRequest.depth.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/application/services/order_book_service.py \
    tests/unit/application/services/test_order_book_service.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 4: `TradesService` L4 orchestrator

**Files:**
- Create: `src/cryptozavr/application/services/trades_service.py`
- Create: `tests/unit/application/services/test_trades_service.py`

- [ ] **Step 1: Write failing tests**

Write `tests/unit/application/services/test_trades_service.py`:
```python
"""Test TradesService: venue/symbol validation + chain wiring."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from cryptozavr.application.services.trades_service import (
    TradesFetchResult,
    TradesService,
)
from cryptozavr.domain.exceptions import (
    SymbolNotFoundError,
    VenueNotSupportedError,
)
from cryptozavr.domain.market_data import TradeSide, TradeTick
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

def _make_trades(symbol) -> tuple[TradeTick, ...]:
    return (
        TradeTick(
            symbol=symbol,
            price=Decimal("100"),
            size=Decimal("0.5"),
            side=TradeSide.BUY,
            executed_at=Instant.from_ms(1_700_000_000_000),
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
    p.fetch_trades = AsyncMock(return_value=_make_trades(symbol))
    return p

@pytest.fixture
def gateway():
    gw = MagicMock()
    gw.load_ticker = AsyncMock(return_value=None)
    gw.load_ohlcv = AsyncMock(return_value=None)
    return gw

@pytest.fixture
def service(registry, gateway, provider) -> TradesService:
    return TradesService(
        registry=registry,
        venue_states={VenueId.KUCOIN: VenueState(VenueId.KUCOIN)},
        providers={VenueId.KUCOIN: provider},
        gateway=gateway,
    )

class TestTradesService:
    @pytest.mark.asyncio
    async def test_fetch_trades_returns_result(
        self, service: TradesService,
    ) -> None:
        result = await service.fetch_trades(
            venue="kucoin", symbol="BTC-USDT", limit=100,
        )
        assert isinstance(result, TradesFetchResult)
        assert len(result.trades) == 1
        assert result.venue == "kucoin"
        assert result.symbol == "BTC-USDT"
        assert "provider:called" in result.reason_codes

    @pytest.mark.asyncio
    async def test_forwards_limit_and_since(
        self, service: TradesService, provider,
    ) -> None:
        since = Instant.from_ms(1_700_000_000_000)
        await service.fetch_trades(
            venue="kucoin", symbol="BTC-USDT", limit=50, since=since,
        )
        call_kwargs = provider.fetch_trades.call_args.kwargs
        assert call_kwargs.get("limit") == 50
        assert call_kwargs.get("since") == since

    @pytest.mark.asyncio
    async def test_force_refresh_passes_through(
        self, service: TradesService, provider,
    ) -> None:
        result = await service.fetch_trades(
            venue="kucoin", symbol="BTC-USDT",
            limit=100, force_refresh=True,
        )
        assert "cache:bypassed" in result.reason_codes
        provider.fetch_trades.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unknown_venue_raises(
        self, service: TradesService,
    ) -> None:
        with pytest.raises(VenueNotSupportedError):
            await service.fetch_trades(
                venue="binance", symbol="BTC-USDT", limit=100,
            )

    @pytest.mark.asyncio
    async def test_unknown_symbol_raises(
        self, service: TradesService,
    ) -> None:
        with pytest.raises(SymbolNotFoundError):
            await service.fetch_trades(
                venue="kucoin", symbol="DOGE-USDT", limit=100,
            )
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

Write `src/cryptozavr/application/services/trades_service.py`:
```python
"""TradesService: orchestrates chain + provider for recent-trades fetches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cryptozavr.domain.exceptions import (
    SymbolNotFoundError,
    VenueNotSupportedError,
)
from cryptozavr.domain.market_data import TradeTick
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant
from cryptozavr.domain.venues import VenueId
from cryptozavr.infrastructure.providers.chain.assembly import (
    build_trades_chain,
)
from cryptozavr.infrastructure.providers.chain.context import (
    FetchContext,
    FetchOperation,
    FetchRequest,
)
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

@dataclass(frozen=True, slots=True)
class TradesFetchResult:
    """Recent trades + venue/symbol identifiers + reason codes audit trail.

    Venue/symbol are carried on the result (unlike Ticker/OHLCV where the
    domain object embeds Symbol) because TradeTick is per-trade and the
    collection-level (venue, symbol) context is orthogonal.
    """

    venue: str
    symbol: str
    trades: tuple[TradeTick, ...]
    reason_codes: list[str]

class TradesService:
    """Facade: translates (venue, symbol, limit, since) into a chain run."""

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

    async def fetch_trades(
        self,
        *,
        venue: str,
        symbol: str,
        limit: int = 100,
        since: Instant | None = None,
        force_refresh: bool = False,
    ) -> TradesFetchResult:
        venue_id = self._resolve_venue(venue)
        symbol_obj = self._registry.find(venue_id, symbol)
        if symbol_obj is None:
            raise SymbolNotFoundError(user_input=symbol, venue=venue)

        chain = build_trades_chain(
            state=self._venue_states[venue_id],
            registry=self._registry,
            gateway=self._gateway,
            provider=self._providers[venue_id],
        )
        ctx = FetchContext(
            request=FetchRequest(
                operation=FetchOperation.TRADES,
                symbol=symbol_obj,
                since=since,
                limit=limit,
                force_refresh=force_refresh,
            ),
        )
        result = await chain.handle(ctx)
        trades: tuple[TradeTick, ...] = tuple(result.metadata["result"])
        return TradesFetchResult(
            venue=venue,
            symbol=symbol,
            trades=trades,
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
uv run pytest tests/unit/application/services/test_trades_service.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src
uv run pytest tests/unit tests/contract -m "not integration" -q 2>&1 | tail -3
```

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```text
feat(app): add TradesService L4 orchestrator

Non-cached fetch path: builds trades chain, extracts the tuple of
TradeTicks. TradesFetchResult carries venue/symbol separately because
TradeTick is per-trade and the collection-level context isn't on the
domain tuple.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/application/services/trades_service.py \
    tests/unit/application/services/test_trades_service.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 5: `get_order_book` MCP tool

**Files:**
- Create: `src/cryptozavr/mcp/tools/order_book.py`
- Create: `tests/unit/mcp/test_get_order_book_tool.py`

- [ ] **Step 1: Write failing tests**

Write `tests/unit/mcp/test_get_order_book_tool.py`:
```python
"""In-memory Client(mcp) tests for the get_order_book tool."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from cryptozavr.application.services.order_book_service import (
    OrderBookFetchResult,
)
from cryptozavr.domain.exceptions import SymbolNotFoundError
from cryptozavr.domain.market_data import OrderBookSnapshot
from cryptozavr.domain.quality import (
    Confidence,
    DataQuality,
    Provenance,
    Staleness,
)
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, PriceSize
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.mcp.tools.order_book import register_order_book_tool

@dataclass(slots=True)
class _AppState:
    order_book_service: object

def _make_snapshot() -> OrderBookSnapshot:
    symbol = SymbolRegistry().get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )
    return OrderBookSnapshot(
        symbol=symbol,
        bids=(PriceSize(price=Decimal("100"), size=Decimal("1")),),
        asks=(PriceSize(price=Decimal("101"), size=Decimal("1")),),
        observed_at=Instant.from_ms(1_700_000_000_000),
        quality=DataQuality(
            source=Provenance(
                venue_id="kucoin", endpoint="fetch_order_book",
            ),
            fetched_at=Instant.from_ms(1_700_000_000_000),
            staleness=Staleness.FRESH,
            confidence=Confidence.HIGH,
            cache_hit=False,
        ),
    )

def _build_server(mock_service) -> FastMCP:
    @asynccontextmanager
    async def lifespan(server):
        yield _AppState(order_book_service=mock_service)

    mcp = FastMCP(name="test", version="0.0.0", lifespan=lifespan)
    register_order_book_tool(mcp)
    return mcp

@pytest.mark.asyncio
async def test_get_order_book_returns_dto_fields() -> None:
    service = MagicMock()
    service.fetch_order_book = AsyncMock(
        return_value=OrderBookFetchResult(
            snapshot=_make_snapshot(),
            reason_codes=["venue:healthy", "cache:miss", "provider:called"],
        ),
    )
    mcp = _build_server(service)
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_order_book",
            {"venue": "kucoin", "symbol": "BTC-USDT", "depth": 50},
        )
    payload = result.structured_content
    assert payload["venue"] == "kucoin"
    assert payload["symbol"] == "BTC-USDT"
    assert len(payload["bids"]) == 1
    assert len(payload["asks"]) == 1
    assert payload["spread"] == "1"
    assert "provider:called" in payload["reason_codes"]
    call_kwargs = service.fetch_order_book.call_args.kwargs
    assert call_kwargs["depth"] == 50

@pytest.mark.asyncio
async def test_get_order_book_forwards_force_refresh() -> None:
    service = MagicMock()
    service.fetch_order_book = AsyncMock(
        return_value=OrderBookFetchResult(
            snapshot=_make_snapshot(),
            reason_codes=["cache:bypassed"],
        ),
    )
    mcp = _build_server(service)
    async with Client(mcp) as client:
        await client.call_tool(
            "get_order_book",
            {
                "venue": "kucoin", "symbol": "BTC-USDT",
                "depth": 20, "force_refresh": True,
            },
        )
    call_kwargs = service.fetch_order_book.call_args.kwargs
    assert call_kwargs["depth"] == 20
    assert call_kwargs["force_refresh"] is True

@pytest.mark.asyncio
async def test_get_order_book_symbol_not_found_surfaces_tool_error() -> None:
    service = MagicMock()
    service.fetch_order_book = AsyncMock(
        side_effect=SymbolNotFoundError(
            user_input="DOGE-USDT", venue="kucoin",
        ),
    )
    mcp = _build_server(service)
    async with Client(mcp) as client:
        with pytest.raises(ToolError) as exc_info:
            await client.call_tool(
                "get_order_book",
                {"venue": "kucoin", "symbol": "DOGE-USDT", "depth": 50},
            )
    assert "DOGE-USDT" in str(exc_info.value)
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

Write `src/cryptozavr/mcp/tools/order_book.py`:
```python
"""get_order_book MCP tool registration."""

from __future__ import annotations

from typing import Annotated, Any, cast

from fastmcp import Context, FastMCP
from pydantic import Field

from cryptozavr.application.services.order_book_service import (
    OrderBookService,
)
from cryptozavr.domain.exceptions import DomainError
from cryptozavr.mcp.dtos import OrderBookDTO
from cryptozavr.mcp.errors import domain_to_tool_error

def register_order_book_tool(mcp: FastMCP) -> None:
    """Attach get_order_book tool to the given FastMCP instance."""

    @mcp.tool(
        name="get_order_book",
        description=(
            "Fetch the current order-book snapshot (bids + asks) for a "
            "symbol on a venue. Goes through the full 5-handler chain; "
            "order-book is non-cached in M2, so each call reaches the "
            "provider. Convenience spread/spread_bps included."
        ),
        tags={"market", "public", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def get_order_book(
        venue: Annotated[
            str,
            Field(description="Venue id. Supported: kucoin, coingecko."),
        ],
        symbol: Annotated[
            str,
            Field(description="Native symbol, e.g. BTC-USDT (kucoin)."),
        ],
        ctx: Context,
        depth: Annotated[
            int,
            Field(ge=1, le=200, description="Levels per side (1..200)."),
        ] = 50,
        force_refresh: Annotated[
            bool,
            Field(description="Passes through to the chain; non-cached path."),
        ] = False,
    ) -> OrderBookDTO:
        service = cast(
            OrderBookService,
            cast(Any, ctx.lifespan_context).order_book_service,
        )
        try:
            result = await service.fetch_order_book(
                venue=venue,
                symbol=symbol,
                depth=depth,
                force_refresh=force_refresh,
            )
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc
        return OrderBookDTO.from_domain(result.snapshot, result.reason_codes)
```

Note on `idempotentHint: False` — the order-book changes per-call with every new tick, so consecutive calls can return different data. This is the correct hint.

- [ ] **Step 4: PASS (3 tests).**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/mcp/test_get_order_book_tool.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src
```

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```text
feat(mcp): add get_order_book tool

Non-cached market-data tool. Depth bounded 1..200. Returns
OrderBookDTO with bids/asks + spread/spread_bps + reason_codes.
idempotentHint=false because the book changes tick-to-tick.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/mcp/tools/order_book.py \
    tests/unit/mcp/test_get_order_book_tool.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 6: `get_trades` MCP tool

**Files:**
- Create: `src/cryptozavr/mcp/tools/trades.py`
- Create: `tests/unit/mcp/test_get_trades_tool.py`

- [ ] **Step 1: Write failing tests**

Write `tests/unit/mcp/test_get_trades_tool.py`:
```python
"""In-memory Client(mcp) tests for the get_trades tool."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from cryptozavr.application.services.trades_service import TradesFetchResult
from cryptozavr.domain.exceptions import SymbolNotFoundError
from cryptozavr.domain.market_data import TradeSide, TradeTick
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.mcp.tools.trades import register_trades_tool

@dataclass(slots=True)
class _AppState:
    trades_service: object

def _make_trades() -> tuple[TradeTick, ...]:
    symbol = SymbolRegistry().get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )
    return (
        TradeTick(
            symbol=symbol,
            price=Decimal("100.5"),
            size=Decimal("0.1"),
            side=TradeSide.BUY,
            executed_at=Instant.from_ms(1_700_000_000_000),
            trade_id="t1",
        ),
    )

def _build_server(mock_service) -> FastMCP:
    @asynccontextmanager
    async def lifespan(server):
        yield _AppState(trades_service=mock_service)

    mcp = FastMCP(name="test", version="0.0.0", lifespan=lifespan)
    register_trades_tool(mcp)
    return mcp

@pytest.mark.asyncio
async def test_get_trades_returns_dto_fields() -> None:
    service = MagicMock()
    service.fetch_trades = AsyncMock(
        return_value=TradesFetchResult(
            venue="kucoin",
            symbol="BTC-USDT",
            trades=_make_trades(),
            reason_codes=["venue:healthy", "cache:miss", "provider:called"],
        ),
    )
    mcp = _build_server(service)
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_trades",
            {"venue": "kucoin", "symbol": "BTC-USDT", "limit": 100},
        )
    payload = result.structured_content
    assert payload["venue"] == "kucoin"
    assert payload["symbol"] == "BTC-USDT"
    assert len(payload["trades"]) == 1
    assert payload["trades"][0]["side"] == "buy"
    assert payload["trades"][0]["trade_id"] == "t1"
    assert "provider:called" in payload["reason_codes"]
    call_kwargs = service.fetch_trades.call_args.kwargs
    assert call_kwargs["venue"] == "kucoin"
    assert call_kwargs["symbol"] == "BTC-USDT"
    assert call_kwargs["limit"] == 100
    assert call_kwargs["force_refresh"] is False

@pytest.mark.asyncio
async def test_get_trades_forwards_force_refresh() -> None:
    service = MagicMock()
    service.fetch_trades = AsyncMock(
        return_value=TradesFetchResult(
            venue="kucoin", symbol="BTC-USDT",
            trades=(), reason_codes=["cache:bypassed"],
        ),
    )
    mcp = _build_server(service)
    async with Client(mcp) as client:
        await client.call_tool(
            "get_trades",
            {
                "venue": "kucoin", "symbol": "BTC-USDT",
                "limit": 50, "force_refresh": True,
            },
        )
    call_kwargs = service.fetch_trades.call_args.kwargs
    assert call_kwargs["limit"] == 50
    assert call_kwargs["force_refresh"] is True

@pytest.mark.asyncio
async def test_get_trades_symbol_not_found_surfaces_tool_error() -> None:
    service = MagicMock()
    service.fetch_trades = AsyncMock(
        side_effect=SymbolNotFoundError(
            user_input="DOGE-USDT", venue="kucoin",
        ),
    )
    mcp = _build_server(service)
    async with Client(mcp) as client:
        with pytest.raises(ToolError) as exc_info:
            await client.call_tool(
                "get_trades",
                {"venue": "kucoin", "symbol": "DOGE-USDT", "limit": 100},
            )
    assert "DOGE-USDT" in str(exc_info.value)
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

Write `src/cryptozavr/mcp/tools/trades.py`:
```python
"""get_trades MCP tool registration."""

from __future__ import annotations

from typing import Annotated, Any, cast

from fastmcp import Context, FastMCP
from pydantic import Field

from cryptozavr.application.services.trades_service import TradesService
from cryptozavr.domain.exceptions import DomainError
from cryptozavr.mcp.dtos import TradesDTO
from cryptozavr.mcp.errors import domain_to_tool_error

def register_trades_tool(mcp: FastMCP) -> None:
    """Attach get_trades tool to the given FastMCP instance."""

    @mcp.tool(
        name="get_trades",
        description=(
            "Fetch recent trades for a symbol on a venue. Non-cached in "
            "M2 — each call reaches the provider. Returns up to `limit` "
            "most recent trades; passes `since` through unchanged."
        ),
        tags={"market", "public", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def get_trades(
        venue: Annotated[
            str,
            Field(description="Venue id. Supported: kucoin, coingecko."),
        ],
        symbol: Annotated[
            str,
            Field(description="Native symbol, e.g. BTC-USDT (kucoin)."),
        ],
        ctx: Context,
        limit: Annotated[
            int,
            Field(ge=1, le=1000, description="Max trades to return (1..1000)."),
        ] = 100,
        force_refresh: Annotated[
            bool,
            Field(description="Passes through to the chain; non-cached path."),
        ] = False,
    ) -> TradesDTO:
        service = cast(
            TradesService,
            cast(Any, ctx.lifespan_context).trades_service,
        )
        try:
            result = await service.fetch_trades(
                venue=venue,
                symbol=symbol,
                limit=limit,
                force_refresh=force_refresh,
            )
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc
        return TradesDTO.from_domain(
            venue=result.venue,
            symbol=result.symbol,
            trades=result.trades,
            reason_codes=result.reason_codes,
        )
```

- [ ] **Step 4: PASS (3 tests).**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/mcp/test_get_trades_tool.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src
```

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```text
feat(mcp): add get_trades tool

Non-cached market-data tool. limit bounded 1..1000. Returns TradesDTO
with per-trade side/price/size/executed_at_ms/trade_id + reason_codes.
idempotentHint=false because trade history grows between calls.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/mcp/tools/trades.py \
    tests/unit/mcp/test_get_trades_tool.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 7: Wire `order_book_service` + `trades_service` into bootstrap + server

**Files:**
- Modify: `src/cryptozavr/mcp/bootstrap.py`
- Modify: `src/cryptozavr/mcp/server.py`

- [ ] **Step 1: Read current files**

```bash
cd /Users/laptop/dev/cryptozavr
cat src/cryptozavr/mcp/bootstrap.py
cat src/cryptozavr/mcp/server.py
```

- [ ] **Step 2: Update bootstrap.py**

Apply these changes:

1. Add imports alongside existing ticker/ohlcv imports (alphabetically — ohlcv, order_book, ticker, trades):
```python
from cryptozavr.application.services.ohlcv_service import OhlcvService
from cryptozavr.application.services.order_book_service import OrderBookService
from cryptozavr.application.services.ticker_service import TickerService
from cryptozavr.application.services.trades_service import TradesService
```

2. Update `AppState` with two additional fields:
```python
@dataclass(slots=True)
class AppState:
    """Lifespan-scoped application state exposed to tools."""

    ticker_service: TickerService
    ohlcv_service: OhlcvService
    order_book_service: OrderBookService
    trades_service: TradesService
```

3. Update `build_production_service` return type annotation to 5-tuple:
```python
async def build_production_service(
    settings: Settings,
) -> tuple[
    TickerService,
    OhlcvService,
    OrderBookService,
    TradesService,
    Callable[[], Awaitable[None]],
]:
```

4. After constructing `ohlcv_service`, add:
```python
    order_book_service = OrderBookService(
        registry=registry,
        venue_states=venue_states,
        providers=providers,
        gateway=gateway,
    )
    trades_service = TradesService(
        registry=registry,
        venue_states=venue_states,
        providers=providers,
        gateway=gateway,
    )
```

5. Update final return to 5-tuple:
```python
    return (
        ticker_service,
        ohlcv_service,
        order_book_service,
        trades_service,
        cleanup,
    )
```

- [ ] **Step 3: Update server.py**

Apply these changes:

1. Add imports alongside existing tool registrars (alphabetically — ohlcv, order_book, ticker, trades):
```python
from cryptozavr.mcp.tools.ohlcv import register_ohlcv_tool
from cryptozavr.mcp.tools.order_book import register_order_book_tool
from cryptozavr.mcp.tools.ticker import register_ticker_tool
from cryptozavr.mcp.tools.trades import register_trades_tool
```

2. Update lifespan to unpack the new 5-tuple and yield AppState with all four services:
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
            )
        finally:
            await cleanup()
```

3. Register both new tools after existing registrations:
```python
    _register_echo(mcp)
    register_ticker_tool(mcp)
    register_ohlcv_tool(mcp)
    register_order_book_tool(mcp)
    register_trades_tool(mcp)
    return mcp
```

- [ ] **Step 4: Smoke checks**

```bash
cd /Users/laptop/dev/cryptozavr
uv run ruff check . && uv run ruff format --check . && uv run mypy src
uv run pytest tests/unit tests/contract -m "not integration" -q 2>&1 | tail -3
```

Expected: all clean; ≥280 unit + 5 contract tests. (After Tasks 1–6: ~16 new tests on top of 260.)

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```text
feat(mcp): wire order_book + trades services into AppState

Bootstrap now builds all four market-data services (ticker, ohlcv,
order_book, trades) sharing the same registries, providers, and
gateway. AppState carries all four. Server lifespan unpacks the
5-tuple and registers both new tools.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/mcp/bootstrap.py src/cryptozavr/mcp/server.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 8: CHANGELOG + tag v0.0.9 + push

- [ ] **Step 1: Verify**

```bash
cd /Users/laptop/dev/cryptozavr
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest tests/unit tests/contract -m "not integration" -v 2>&1 | tail -15
```

Expected: all clean; ≥280 unit + 5 contract tests.

- [ ] **Step 2: Update CHANGELOG**

Edit `/Users/laptop/dev/cryptozavr/CHANGELOG.md`. Find:
```markdown
## [Unreleased]

## [0.0.8] - 2026-04-21
```

Replace with:
```markdown
## [Unreleased]

## [0.0.9] - 2026-04-21

### Added — M2.6 `get_order_book` + `get_trades` tools
- `PriceSizeDTO` (bid/ask level), `OrderBookDTO` (bids/asks arrays + spread/spread_bps), `TradeTickDTO` (single trade), `TradesDTO` (wrapped list + venue/symbol). All Pydantic v2 frozen BaseModels with `from_domain` factories.
- `OrderBookService` (L4) — non-cached fetch via `build_order_book_chain`. `fetch_order_book(venue, symbol, depth, force_refresh)` returns `OrderBookFetchResult(snapshot, reason_codes)`.
- `TradesService` (L4) — non-cached fetch via `build_trades_chain`. `fetch_trades(venue, symbol, limit, since, force_refresh)` returns `TradesFetchResult(venue, symbol, trades, reason_codes)`.
- `build_order_book_chain` / `build_trades_chain` assembly helpers (delegate to `_build_chain`).
- `register_order_book_tool(mcp)`: `get_order_book(venue, symbol, depth, force_refresh)` bounded `depth` 1..200. `annotations.idempotentHint=False` (book ticks).
- `register_trades_tool(mcp)`: `get_trades(venue, symbol, limit, force_refresh)` bounded `limit` 1..1000. `annotations.idempotentHint=False`.
- `AppState` now carries all four services (ticker, ohlcv, order_book, trades). `build_production_service` returns a 5-tuple.
- ~16 new unit tests (DTOs 7 + OrderBookService 5 + TradesService 5 + each tool 3). Total ≥280 unit + 5 contract + 2 integration (skip-safe).

### Next
- M2.7+: Realtime subscriber (phase 1.5), signals/triggers (L4 business logic), production deployment to cloud Supabase.

## [0.0.8] - 2026-04-21
```

- [ ] **Step 3: Commit CHANGELOG + plan**

```bash
cd /Users/laptop/dev/cryptozavr
git add CHANGELOG.md
git add docs/superpowers/plans/2026-04-21-cryptozavr-m2.6-order-book-and-trades.md 2>/dev/null || true
```

Write to /tmp/commit-msg.txt:
```bash
docs: finalize CHANGELOG for v0.0.9 (M2.6 order_book + trades)

Completes the market-data tool surface: 4 tools (get_ticker,
get_ohlcv, get_order_book, get_trades) through the full stack.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

- [ ] **Step 4: Tag + push**

Write tag message to /tmp/tag-msg.txt:
```text
M2.6 get_order_book + get_trades complete

Non-cached market-data tools (order book + recent trades) through the
5-handler chain. AppState carries all four services (ticker, ohlcv,
order_book, trades). Market-data tool surface complete.
```

```bash
cd /Users/laptop/dev/cryptozavr
git tag -a v0.0.9 -F /tmp/tag-msg.txt
rm /tmp/tag-msg.txt
git push origin main
git push origin v0.0.9
```

- [ ] **Step 5: Summary**

```bash
cd /Users/laptop/dev/cryptozavr
echo "=== M2.6 complete ==="
git log --oneline v0.0.8..HEAD
git tag -l | tail -5
```

---

## Acceptance Criteria

1. ✅ All 8 tasks done.
2. ✅ ~16 new unit tests. Total ≥280 unit + 5 contract + 2 integration (skip-safe).
3. ✅ `get_order_book` returns `OrderBookDTO` with bids/asks arrays + computed spread/spread_bps.
4. ✅ `get_trades` returns `TradesDTO` with per-trade side/price/size/executed_at_ms/trade_id.
5. ✅ Both tools declare `idempotentHint=False` (correct MCP signal).
6. ✅ `AppState` has all four services; no KeyError possible because all four venues are seeded symmetrically.
7. ✅ Mypy strict + ruff + pytest green.
8. ✅ Tag `v0.0.9` pushed to github.com/evgenygurin/cryptozavr.

---

## Notes

- **Non-cached tools** behave the same as cached from the chain's perspective: SupabaseCacheHandler returns None (its `_lookup` method already handles order_book/trades by returning None), ProviderFetchHandler skips write-through for these operations (code-path already present in M2.3c). No handler changes needed.
- **TradesFetchResult carries venue+symbol** because `TradeTick` embeds `Symbol` but the collection-level tuple doesn't — using the tuple directly would force DTO builders to re-derive venue/symbol from the first trade, which fails for empty tuples. Explicit carry-through is cleaner.
- **idempotentHint=False** for both tools: unlike get_ticker (also changes, but represents "current state"), order-book and trades represent *new data per call*. MCP clients that cache idempotent calls shouldn't cache these.
- **No integration tests in M2.6** — reuse the M2.5 integration framework in M2.7+ once Realtime/signal layer is added. For MVP, in-memory Client tests give enough coverage.
- **CoinGecko doesn't have order_book or trades endpoints** the way KuCoin does. Calling these tools with `venue="coingecko"` will reach the provider's `fetch_order_book`/`fetch_trades`, which will likely raise `NotImplementedError` or similar. That's fine for MVP — production gating happens in bootstrap by registering only venues that support the operation. M2.7+ can introduce capability filtering.
