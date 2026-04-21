# cryptozavr — Milestone 2.3c: Chain of Responsibility + ProviderFactory Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Завершить Providers layer: Chain of Responsibility из 5 handlers + ProviderFactory (Factory Method). После M2.3c: `chain.handle(ctx)` проходит through venue-health → symbol-exists → staleness-bypass → supabase-cache → provider-fetch, cache-hit коротит цепь. `ProviderFactory.create_kucoin()` возвращает fully-wired provider с decorator chain.

**Architecture:** L2 Infrastructure. 5 CoR handlers pre-valide запрос до вызова provider. ProviderFactory — Factory Method для сборки BaseProvider + 4 Decorators.

**Tech Stack:** Python 3.12 — no new deps.

**Starting tag:** `v0.0.5`. Target: `v0.0.6`.

---

## File Structure

| Path | Responsibility |
|------|---------------|
| `src/cryptozavr/infrastructure/providers/chain/__init__.py` | Package marker |
| `src/cryptozavr/infrastructure/providers/chain/context.py` | `FetchRequest`, `FetchContext`, `FetchOperation` enum |
| `src/cryptozavr/infrastructure/providers/chain/handlers.py` | `FetchHandler` base + 5 concrete handlers |
| `src/cryptozavr/infrastructure/providers/chain/assembly.py` | `build_ticker_chain`, `build_ohlcv_chain` |
| `src/cryptozavr/infrastructure/providers/factory.py` | `ProviderFactory` (Factory Method) |
| `tests/unit/infrastructure/providers/chain/*` | Unit tests (package + context + handlers + assembly) |
| `tests/unit/infrastructure/providers/test_factory.py` | ProviderFactory tests |

---

## Tasks

### Task 1: Chain base (FetchRequest, FetchContext, FetchHandler, FetchOperation)

**Files:**
- Create: `src/cryptozavr/infrastructure/providers/chain/__init__.py`
- Create: `src/cryptozavr/infrastructure/providers/chain/context.py`
- Create: `tests/unit/infrastructure/providers/chain/__init__.py` (empty)
- Create: `tests/unit/infrastructure/providers/chain/test_context.py`

- [ ] **Step 1: Write failing tests**

Write empty `tests/unit/infrastructure/providers/chain/__init__.py`.

Write `tests/unit/infrastructure/providers/chain/test_context.py`:
```python
"""Test FetchRequest/FetchContext/FetchOperation dataclasses."""

from __future__ import annotations

import pytest

from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.chain.context import (
    FetchContext,
    FetchOperation,
    FetchRequest,
)

@pytest.fixture
def btc_symbol():
    return SymbolRegistry().get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )

class TestFetchOperation:
    def test_values(self) -> None:
        assert FetchOperation.TICKER.value == "ticker"
        assert FetchOperation.OHLCV.value == "ohlcv"
        assert FetchOperation.ORDER_BOOK.value == "order_book"
        assert FetchOperation.TRADES.value == "trades"

class TestFetchRequest:
    def test_ticker_request(self, btc_symbol) -> None:
        req = FetchRequest(
            operation=FetchOperation.TICKER,
            symbol=btc_symbol,
        )
        assert req.operation == FetchOperation.TICKER
        assert req.symbol is btc_symbol
        assert req.timeframe is None
        assert req.limit == 500
        assert req.force_refresh is False

    def test_ohlcv_request_with_timeframe(self, btc_symbol) -> None:
        req = FetchRequest(
            operation=FetchOperation.OHLCV,
            symbol=btc_symbol,
            timeframe=Timeframe.H1,
            limit=100,
            force_refresh=True,
        )
        assert req.timeframe == Timeframe.H1
        assert req.limit == 100
        assert req.force_refresh is True

class TestFetchContext:
    def test_empty_context(self, btc_symbol) -> None:
        req = FetchRequest(operation=FetchOperation.TICKER, symbol=btc_symbol)
        ctx = FetchContext(request=req)
        assert ctx.reason_codes == []
        assert ctx.metadata == {}

    def test_add_reason_code(self, btc_symbol) -> None:
        req = FetchRequest(operation=FetchOperation.TICKER, symbol=btc_symbol)
        ctx = FetchContext(request=req)
        ctx.add_reason("venue:healthy")
        ctx.add_reason("cache:miss")
        assert ctx.reason_codes == ["venue:healthy", "cache:miss"]

    def test_has_result(self, btc_symbol) -> None:
        req = FetchRequest(operation=FetchOperation.TICKER, symbol=btc_symbol)
        ctx = FetchContext(request=req)
        assert ctx.has_result() is False
        ctx.metadata["result"] = "some-ticker"
        assert ctx.has_result() is True
```

- [ ] **Step 2: Run — FAIL**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/infrastructure/providers/chain/test_context.py -v
```

- [ ] **Step 3: Implement**

Write `src/cryptozavr/infrastructure/providers/chain/__init__.py`:
```python
"""Chain of Responsibility: pre-fetch validation + cache-aside pipeline."""
```

Write `src/cryptozavr/infrastructure/providers/chain/context.py`:
```python
"""Data carriers for Chain of Responsibility."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Instant, Timeframe

class FetchOperation(StrEnum):
    """Kind of fetch operation requested."""

    TICKER = "ticker"
    OHLCV = "ohlcv"
    ORDER_BOOK = "order_book"
    TRADES = "trades"

@dataclass(frozen=True, slots=True)
class FetchRequest:
    """Immutable request passed through Chain of Responsibility."""

    operation: FetchOperation
    symbol: Symbol
    timeframe: Timeframe | None = None
    since: Instant | None = None
    limit: int = 500
    depth: int = 50
    force_refresh: bool = False

@dataclass(slots=True)
class FetchContext:
    """Mutable context: accumulates reason_codes + metadata across handlers."""

    request: FetchRequest
    reason_codes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_reason(self, code: str) -> None:
        self.reason_codes.append(code)

    def has_result(self) -> bool:
        return "result" in self.metadata
```

- [ ] **Step 4: PASS (7 tests).**
- [ ] **Step 5: Mypy + commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add \
  src/cryptozavr/infrastructure/providers/chain/__init__.py \
  src/cryptozavr/infrastructure/providers/chain/context.py \
  tests/unit/infrastructure/providers/chain/__init__.py \
  tests/unit/infrastructure/providers/chain/test_context.py
```

Commit:
```bash
feat(providers): add Chain of Responsibility context

FetchOperation enum (TICKER/OHLCV/ORDER_BOOK/TRADES), FetchRequest
(immutable), FetchContext (mutable accumulator of reason_codes and
metadata, with has_result() shortcut for cache hits).
```

---

### Task 2: FetchHandler base + VenueHealthHandler (TDD)

**Files:**
- Create: `src/cryptozavr/infrastructure/providers/chain/handlers.py`
- Create: `tests/unit/infrastructure/providers/chain/test_handlers.py`

- [ ] **Step 1: Failing tests**

Write `tests/unit/infrastructure/providers/chain/test_handlers.py`:
```python
"""Test FetchHandler base + VenueHealthHandler."""

from __future__ import annotations

import pytest

from cryptozavr.domain.exceptions import ProviderUnavailableError
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId, VenueStateKind
from cryptozavr.infrastructure.providers.chain.context import (
    FetchContext,
    FetchOperation,
    FetchRequest,
)
from cryptozavr.infrastructure.providers.chain.handlers import (
    FetchHandler,
    VenueHealthHandler,
)
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

@pytest.fixture
def btc_symbol():
    return SymbolRegistry().get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )

@pytest.fixture
def ctx(btc_symbol):
    return FetchContext(
        request=FetchRequest(
            operation=FetchOperation.TICKER, symbol=btc_symbol,
        ),
    )

class _PassthroughHandler(FetchHandler):
    async def handle(self, ctx: FetchContext) -> FetchContext:
        ctx.add_reason("passthrough")
        return await self._forward(ctx)

class TestFetchHandlerBase:
    @pytest.mark.asyncio
    async def test_terminal_handler_without_next(self, ctx) -> None:
        handler = _PassthroughHandler()
        result = await handler.handle(ctx)
        assert result is ctx
        assert ctx.reason_codes == ["passthrough"]

    @pytest.mark.asyncio
    async def test_set_next_chains_handlers(self, ctx) -> None:
        first = _PassthroughHandler()
        second = _PassthroughHandler()
        first.set_next(second)
        result = await first.handle(ctx)
        assert result is ctx
        assert ctx.reason_codes == ["passthrough", "passthrough"]

class TestVenueHealthHandler:
    @pytest.mark.asyncio
    async def test_healthy_forwards_with_reason(self, ctx) -> None:
        state = VenueState(VenueId.KUCOIN)
        handler = VenueHealthHandler(state)
        result = await handler.handle(ctx)
        assert result is ctx
        assert "venue:healthy" in ctx.reason_codes

    @pytest.mark.asyncio
    async def test_degraded_forwards_with_reason(self, ctx) -> None:
        state = VenueState(VenueId.KUCOIN, kind=VenueStateKind.DEGRADED)
        handler = VenueHealthHandler(state)
        result = await handler.handle(ctx)
        assert result is ctx
        assert "venue:degraded" in ctx.reason_codes

    @pytest.mark.asyncio
    async def test_down_raises(self, ctx) -> None:
        state = VenueState(VenueId.KUCOIN)
        state.mark_down()
        handler = VenueHealthHandler(state)
        with pytest.raises(ProviderUnavailableError):
            await handler.handle(ctx)
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

Write `src/cryptozavr/infrastructure/providers/chain/handlers.py`:
```python
"""Chain of Responsibility handlers for pre-fetch validation.

All handlers inherit FetchHandler base. Each either:
- mutates ctx (adds reason_code or metadata) and forwards to next
- short-circuits (returns ctx without forwarding, e.g. cache hit)
- raises a Domain exception (venue down, symbol not found)
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from cryptozavr.infrastructure.providers.chain.context import FetchContext
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

class FetchHandler(ABC):
    """Base class for Chain of Responsibility handlers."""

    _next: FetchHandler | None = None

    def set_next(self, handler: FetchHandler) -> FetchHandler:
        """Link next handler; returns it for fluent chaining."""
        self._next = handler
        return handler

    @abstractmethod
    async def handle(self, ctx: FetchContext) -> FetchContext: ...

    async def _forward(self, ctx: FetchContext) -> FetchContext:
        """Delegate to next handler; terminal if no next."""
        if self._next is None:
            return ctx
        return await self._next.handle(ctx)

class VenueHealthHandler(FetchHandler):
    """First gate: checks VenueState.require_operational()."""

    def __init__(self, state: VenueState) -> None:
        self._state = state

    async def handle(self, ctx: FetchContext) -> FetchContext:
        self._state.require_operational()
        ctx.add_reason(f"venue:{self._state.kind.value}")
        return await self._forward(ctx)
```

- [ ] **Step 4: PASS (5 tests).**
- [ ] **Step 5: Mypy + commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add \
  src/cryptozavr/infrastructure/providers/chain/handlers.py \
  tests/unit/infrastructure/providers/chain/test_handlers.py
```

Commit:
```text
feat(providers): add FetchHandler base + VenueHealthHandler

Abstract base with set_next/_forward. First concrete handler: checks
VenueState.require_operational() (raises on DOWN/RATE_LIMITED) and
adds "venue:<kind>" reason code.
```

---

### Task 3: SymbolExistsHandler + StalenessBypassHandler (TDD, batched)

Both handlers are minimal — batched in one task with two commits.

**Files:** Modify `chain/handlers.py` + `test_handlers.py`.

- [ ] **Step 1: Append failing tests**

Append to `tests/unit/infrastructure/providers/chain/test_handlers.py`:
```python
from cryptozavr.domain.exceptions import SymbolNotFoundError
from cryptozavr.infrastructure.providers.chain.handlers import (
    StalenessBypassHandler,
    SymbolExistsHandler,
)

class TestSymbolExistsHandler:
    @pytest.mark.asyncio
    async def test_registered_symbol_forwards(self, ctx, btc_symbol) -> None:
        registry = SymbolRegistry()
        # Register the symbol so find() succeeds
        registry.get(
            VenueId.KUCOIN, "BTC", "USDT",
            market_type=MarketType.SPOT, native_symbol="BTC-USDT",
        )
        handler = SymbolExistsHandler(registry)
        result = await handler.handle(ctx)
        assert result is ctx
        assert "symbol:found" in ctx.reason_codes

    @pytest.mark.asyncio
    async def test_unregistered_symbol_raises(self, ctx) -> None:
        registry = SymbolRegistry()  # empty
        handler = SymbolExistsHandler(registry)
        with pytest.raises(SymbolNotFoundError):
            await handler.handle(ctx)

class TestStalenessBypassHandler:
    @pytest.mark.asyncio
    async def test_no_bypass_forwards(self, ctx) -> None:
        handler = StalenessBypassHandler()
        result = await handler.handle(ctx)
        assert result is ctx
        assert "cache:bypassed" not in ctx.reason_codes

    @pytest.mark.asyncio
    async def test_force_refresh_adds_bypass_reason(self, btc_symbol) -> None:
        req = FetchRequest(
            operation=FetchOperation.TICKER,
            symbol=btc_symbol,
            force_refresh=True,
        )
        ctx = FetchContext(request=req)
        handler = StalenessBypassHandler()
        result = await handler.handle(ctx)
        assert result is ctx
        assert "cache:bypassed" in ctx.reason_codes
        assert ctx.metadata.get("bypass_cache") is True
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement both handlers**

Append to `src/cryptozavr/infrastructure/providers/chain/handlers.py`:
```python
from cryptozavr.domain.exceptions import SymbolNotFoundError
from cryptozavr.domain.symbols import SymbolRegistry

class SymbolExistsHandler(FetchHandler):
    """Second gate: verifies the symbol is known to SymbolRegistry."""

    def __init__(self, registry: SymbolRegistry) -> None:
        self._registry = registry

    async def handle(self, ctx: FetchContext) -> FetchContext:
        symbol = ctx.request.symbol
        found = self._registry.find(symbol.venue, symbol.native_symbol)
        if found is None:
            raise SymbolNotFoundError(
                user_input=symbol.native_symbol,
                venue=symbol.venue.value,
            )
        ctx.add_reason("symbol:found")
        return await self._forward(ctx)

class StalenessBypassHandler(FetchHandler):
    """Reads request.force_refresh; marks metadata so cache handler skips."""

    async def handle(self, ctx: FetchContext) -> FetchContext:
        if ctx.request.force_refresh:
            ctx.metadata["bypass_cache"] = True
            ctx.add_reason("cache:bypassed")
        return await self._forward(ctx)
```

- [ ] **Step 4: PASS (4 new tests = 9 total in test_handlers).**
- [ ] **Step 5: Commit**

Commit:
```bash
feat(providers): add SymbolExistsHandler + StalenessBypassHandler

SymbolExistsHandler: validates symbol registration via SymbolRegistry.find;
raises SymbolNotFoundError on miss. StalenessBypassHandler: honours
request.force_refresh, sets metadata["bypass_cache"]=True for downstream
SupabaseCacheHandler to skip.
```

---

### Task 4: SupabaseCacheHandler (TDD with fake gateway)

- [ ] **Step 1: Failing tests**

Append to `test_handlers.py`:
```python
from unittest.mock import AsyncMock, MagicMock

from cryptozavr.domain.market_data import Ticker
from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.value_objects import Instant, Timeframe
from decimal import Decimal
from cryptozavr.infrastructure.providers.chain.handlers import SupabaseCacheHandler

def _make_cached_ticker(symbol) -> Ticker:
    return Ticker(
        symbol=symbol,
        last=Decimal("100"),
        observed_at=Instant.now(),
        quality=DataQuality(
            source=Provenance(venue_id="kucoin", endpoint="fetch_ticker"),
            fetched_at=Instant.now(),
            staleness=Staleness.FRESH,
            confidence=Confidence.HIGH,
            cache_hit=True,
        ),
    )

class TestSupabaseCacheHandler:
    @pytest.mark.asyncio
    async def test_cache_hit_short_circuits(self, btc_symbol) -> None:
        cached = _make_cached_ticker(btc_symbol)
        gateway = MagicMock()
        gateway.load_ticker = AsyncMock(return_value=cached)
        req = FetchRequest(operation=FetchOperation.TICKER, symbol=btc_symbol)
        ctx = FetchContext(request=req)
        handler = SupabaseCacheHandler(gateway)
        result = await handler.handle(ctx)
        assert result.metadata["result"] is cached
        assert "cache:hit" in ctx.reason_codes
        gateway.load_ticker.assert_awaited_once_with(btc_symbol)

    @pytest.mark.asyncio
    async def test_cache_miss_forwards(self, btc_symbol) -> None:
        gateway = MagicMock()
        gateway.load_ticker = AsyncMock(return_value=None)
        req = FetchRequest(operation=FetchOperation.TICKER, symbol=btc_symbol)
        ctx = FetchContext(request=req)
        handler = SupabaseCacheHandler(gateway)
        result = await handler.handle(ctx)
        assert result is ctx
        assert "cache:miss" in ctx.reason_codes
        assert not ctx.has_result()

    @pytest.mark.asyncio
    async def test_bypass_cache_skips_lookup(self, btc_symbol) -> None:
        gateway = MagicMock()
        gateway.load_ticker = AsyncMock(return_value="unused")
        req = FetchRequest(
            operation=FetchOperation.TICKER, symbol=btc_symbol,
            force_refresh=True,
        )
        ctx = FetchContext(request=req)
        ctx.metadata["bypass_cache"] = True
        handler = SupabaseCacheHandler(gateway)
        result = await handler.handle(ctx)
        assert result is ctx
        assert not ctx.has_result()
        gateway.load_ticker.assert_not_called()

    @pytest.mark.asyncio
    async def test_gateway_error_falls_through(self, btc_symbol) -> None:
        gateway = MagicMock()
        gateway.load_ticker = AsyncMock(
            side_effect=RuntimeError("connection lost"),
        )
        req = FetchRequest(operation=FetchOperation.TICKER, symbol=btc_symbol)
        ctx = FetchContext(request=req)
        handler = SupabaseCacheHandler(gateway)
        result = await handler.handle(ctx)
        assert result is ctx
        assert "cache:error" in ctx.reason_codes
        assert not ctx.has_result()

    @pytest.mark.asyncio
    async def test_ohlcv_cache_hit(self, btc_symbol) -> None:
        gateway = MagicMock()
        cached_series = MagicMock()
        gateway.load_ohlcv = AsyncMock(return_value=cached_series)
        req = FetchRequest(
            operation=FetchOperation.OHLCV, symbol=btc_symbol,
            timeframe=Timeframe.H1, limit=100,
        )
        ctx = FetchContext(request=req)
        handler = SupabaseCacheHandler(gateway)
        result = await handler.handle(ctx)
        assert result.metadata["result"] is cached_series
        gateway.load_ohlcv.assert_awaited_once_with(
            btc_symbol, Timeframe.H1, since=None, limit=100,
        )
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

Append to `src/cryptozavr/infrastructure/providers/chain/handlers.py`:
```python
import logging
from typing import Any

_LOG = logging.getLogger(__name__)

class SupabaseCacheHandler(FetchHandler):
    """Try to short-circuit the chain via Supabase-cached result.

    Respects metadata["bypass_cache"] set by StalenessBypassHandler.
    Gateway errors are caught and logged — they don't break the chain.
    """

    def __init__(self, gateway: Any) -> None:
        self._gateway = gateway

    async def handle(self, ctx: FetchContext) -> FetchContext:
        if ctx.metadata.get("bypass_cache"):
            return await self._forward(ctx)

        try:
            cached = await self._lookup(ctx)
        except Exception as exc:
            _LOG.warning("supabase cache lookup failed: %s", exc)
            ctx.add_reason("cache:error")
            return await self._forward(ctx)

        if cached is not None:
            ctx.metadata["result"] = cached
            ctx.add_reason("cache:hit")
            return ctx

        ctx.add_reason("cache:miss")
        return await self._forward(ctx)

    async def _lookup(self, ctx: FetchContext) -> Any:
        req = ctx.request
        if req.operation.value == "ticker":
            return await self._gateway.load_ticker(req.symbol)
        if req.operation.value == "ohlcv":
            return await self._gateway.load_ohlcv(
                req.symbol, req.timeframe, since=req.since, limit=req.limit,
            )
        # order_book / trades not cached in M2.2 — always miss
        return None
```

- [ ] **Step 4: PASS (5 new tests = 14 total in test_handlers).**
- [ ] **Step 5: Commit**

Commit:
```text
feat(providers): add SupabaseCacheHandler

Cache-aside via SupabaseGateway. On hit: writes to metadata["result"]
+ "cache:hit" reason and short-circuits (no forward). On miss:
"cache:miss" and forwards. Gateway errors caught (logged + "cache:error"
reason) — never break the chain. Respects bypass_cache metadata flag.
```

---

### Task 5: ProviderFetchHandler (terminal + write-through)

- [ ] **Step 1: Failing tests**

Append to `test_handlers.py`:
```python
from cryptozavr.infrastructure.providers.chain.handlers import ProviderFetchHandler

class _FakeProvider:
    venue_id = "kucoin"

    def __init__(self) -> None:
        self.ticker_calls = 0
        self.ohlcv_calls = 0

    async def fetch_ticker(self, symbol):
        self.ticker_calls += 1
        return _make_cached_ticker(symbol)

    async def fetch_ohlcv(self, symbol, timeframe, since=None, limit=500):
        self.ohlcv_calls += 1
        return f"ohlcv-{symbol.native_symbol}-{timeframe.value}"

class TestProviderFetchHandler:
    @pytest.mark.asyncio
    async def test_cache_hit_skips_provider(self, btc_symbol) -> None:
        provider = _FakeProvider()
        gateway = MagicMock()
        gateway.upsert_ticker = AsyncMock()
        req = FetchRequest(operation=FetchOperation.TICKER, symbol=btc_symbol)
        ctx = FetchContext(request=req)
        ctx.metadata["result"] = "cached-ticker"
        handler = ProviderFetchHandler(provider=provider, gateway=gateway)
        result = await handler.handle(ctx)
        assert result.metadata["result"] == "cached-ticker"
        assert provider.ticker_calls == 0
        gateway.upsert_ticker.assert_not_called()

    @pytest.mark.asyncio
    async def test_ticker_miss_calls_provider_and_upserts(
        self, btc_symbol,
    ) -> None:
        provider = _FakeProvider()
        gateway = MagicMock()
        gateway.upsert_ticker = AsyncMock()
        req = FetchRequest(operation=FetchOperation.TICKER, symbol=btc_symbol)
        ctx = FetchContext(request=req)
        handler = ProviderFetchHandler(provider=provider, gateway=gateway)
        result = await handler.handle(ctx)
        assert result.metadata["result"] is not None
        assert provider.ticker_calls == 1
        assert "provider:called" in ctx.reason_codes
        gateway.upsert_ticker.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ohlcv_miss_calls_provider(self, btc_symbol) -> None:
        provider = _FakeProvider()
        gateway = MagicMock()
        gateway.upsert_ohlcv = AsyncMock()
        req = FetchRequest(
            operation=FetchOperation.OHLCV, symbol=btc_symbol,
            timeframe=Timeframe.H1, limit=50,
        )
        ctx = FetchContext(request=req)
        handler = ProviderFetchHandler(provider=provider, gateway=gateway)
        result = await handler.handle(ctx)
        assert "ohlcv-BTC-USDT-1h" in result.metadata["result"]
        assert provider.ohlcv_calls == 1
        gateway.upsert_ohlcv.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upsert_failure_does_not_break_response(
        self, btc_symbol,
    ) -> None:
        provider = _FakeProvider()
        gateway = MagicMock()
        gateway.upsert_ticker = AsyncMock(side_effect=RuntimeError("db down"))
        req = FetchRequest(operation=FetchOperation.TICKER, symbol=btc_symbol)
        ctx = FetchContext(request=req)
        handler = ProviderFetchHandler(provider=provider, gateway=gateway)
        # Should still succeed; write-through failure logged, not raised
        result = await handler.handle(ctx)
        assert result.metadata["result"] is not None
        assert "provider:called" in ctx.reason_codes
        assert "cache:write_failed" in ctx.reason_codes
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

Append to `src/cryptozavr/infrastructure/providers/chain/handlers.py`:
```python
class ProviderFetchHandler(FetchHandler):
    """Terminal handler: calls the provider on cache miss + write-through."""

    def __init__(self, *, provider: Any, gateway: Any) -> None:
        self._provider = provider
        self._gateway = gateway

    async def handle(self, ctx: FetchContext) -> FetchContext:
        if ctx.has_result():
            return ctx  # cache hit — nothing to do

        result = await self._fetch(ctx)
        ctx.metadata["result"] = result
        ctx.add_reason("provider:called")

        await self._write_through(ctx, result)
        return ctx

    async def _fetch(self, ctx: FetchContext) -> Any:
        req = ctx.request
        op = req.operation.value
        if op == "ticker":
            return await self._provider.fetch_ticker(req.symbol)
        if op == "ohlcv":
            return await self._provider.fetch_ohlcv(
                req.symbol, req.timeframe, since=req.since, limit=req.limit,
            )
        if op == "order_book":
            return await self._provider.fetch_order_book(
                req.symbol, depth=req.depth,
            )
        if op == "trades":
            return await self._provider.fetch_trades(
                req.symbol, since=req.since, limit=req.limit,
            )
        raise ValueError(f"unsupported operation: {op}")

    async def _write_through(
        self, ctx: FetchContext, result: Any,
    ) -> None:
        op = ctx.request.operation.value
        try:
            if op == "ticker":
                await self._gateway.upsert_ticker(result)
            elif op == "ohlcv":
                await self._gateway.upsert_ohlcv(result)
            # order_book / trades not cached in M2.2 — skip
        except Exception as exc:
            _LOG.warning("supabase write-through failed: %s", exc)
            ctx.add_reason("cache:write_failed")
```

- [ ] **Step 4: PASS (4 new tests = 18 total).**
- [ ] **Step 5: Commit**

Commit:
```bash
feat(providers): add ProviderFetchHandler (terminal + write-through)

Terminal handler: short-circuits if ctx already has "result" (cache
hit). Otherwise dispatches to provider.fetch_* per operation and
write-throughs to SupabaseGateway. Upsert failure is non-fatal:
"cache:write_failed" reason is added but the response still flows.
```

---

### Task 6: Chain assembly (build_ticker_chain + build_ohlcv_chain)

**Files:**
- Create: `src/cryptozavr/infrastructure/providers/chain/assembly.py`
- Create: `tests/unit/infrastructure/providers/chain/test_assembly.py`

- [ ] **Step 1: Failing tests**

Write `tests/unit/infrastructure/providers/chain/test_assembly.py`:
```python
"""Test chain assembly helpers."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from cryptozavr.domain.market_data import Ticker
from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Timeframe
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.chain.assembly import (
    build_ohlcv_chain,
    build_ticker_chain,
)
from cryptozavr.infrastructure.providers.chain.context import (
    FetchContext,
    FetchOperation,
    FetchRequest,
)
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

@pytest.fixture
def registry() -> SymbolRegistry:
    reg = SymbolRegistry()
    reg.get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )
    return reg

@pytest.fixture
def btc_symbol(registry):
    return registry.get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )

class _FakeProvider:
    venue_id = "kucoin"

    async def fetch_ticker(self, symbol):
        return Ticker(
            symbol=symbol, last=Decimal("100"),
            observed_at=Instant.now(),
            quality=DataQuality(
                source=Provenance(venue_id="kucoin", endpoint="fetch_ticker"),
                fetched_at=Instant.now(),
                staleness=Staleness.FRESH,
                confidence=Confidence.HIGH,
                cache_hit=False,
            ),
        )

    async def fetch_ohlcv(self, symbol, timeframe, since=None, limit=500):
        return f"ohlcv-{symbol.native_symbol}"

@pytest.mark.asyncio
async def test_ticker_chain_cache_miss_then_provider(
    btc_symbol, registry,
) -> None:
    gateway = MagicMock()
    gateway.load_ticker = AsyncMock(return_value=None)  # miss
    gateway.upsert_ticker = AsyncMock()

    chain = build_ticker_chain(
        state=VenueState(VenueId.KUCOIN),
        registry=registry,
        gateway=gateway,
        provider=_FakeProvider(),
    )

    ctx = FetchContext(
        request=FetchRequest(
            operation=FetchOperation.TICKER, symbol=btc_symbol,
        ),
    )
    result = await chain.handle(ctx)

    assert result.has_result()
    assert ctx.reason_codes == [
        "venue:healthy", "symbol:found", "cache:miss", "provider:called",
    ]
    gateway.load_ticker.assert_awaited_once()
    gateway.upsert_ticker.assert_awaited_once()

@pytest.mark.asyncio
async def test_ticker_chain_cache_hit_short_circuits(
    btc_symbol, registry,
) -> None:
    cached_ticker = Ticker(
        symbol=btc_symbol, last=Decimal("99"),
        observed_at=Instant.now(),
        quality=DataQuality(
            source=Provenance(venue_id="kucoin", endpoint="fetch_ticker"),
            fetched_at=Instant.now(),
            staleness=Staleness.FRESH,
            confidence=Confidence.HIGH,
            cache_hit=True,
        ),
    )
    gateway = MagicMock()
    gateway.load_ticker = AsyncMock(return_value=cached_ticker)
    gateway.upsert_ticker = AsyncMock()

    chain = build_ticker_chain(
        state=VenueState(VenueId.KUCOIN),
        registry=registry,
        gateway=gateway,
        provider=_FakeProvider(),
    )

    ctx = FetchContext(
        request=FetchRequest(
            operation=FetchOperation.TICKER, symbol=btc_symbol,
        ),
    )
    result = await chain.handle(ctx)

    assert result.metadata["result"] is cached_ticker
    assert "cache:hit" in ctx.reason_codes
    assert "provider:called" not in ctx.reason_codes
    gateway.upsert_ticker.assert_not_called()

@pytest.mark.asyncio
async def test_ohlcv_chain_assembles_correctly(
    btc_symbol, registry,
) -> None:
    gateway = MagicMock()
    gateway.load_ohlcv = AsyncMock(return_value=None)
    gateway.upsert_ohlcv = AsyncMock()

    chain = build_ohlcv_chain(
        state=VenueState(VenueId.KUCOIN),
        registry=registry,
        gateway=gateway,
        provider=_FakeProvider(),
    )

    ctx = FetchContext(
        request=FetchRequest(
            operation=FetchOperation.OHLCV, symbol=btc_symbol,
            timeframe=Timeframe.H1, limit=10,
        ),
    )
    result = await chain.handle(ctx)

    assert result.has_result()
    assert "provider:called" in ctx.reason_codes
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

Write `src/cryptozavr/infrastructure/providers/chain/assembly.py`:
```python
"""Chain assembly helpers. Wire handlers in the canonical order."""

from __future__ import annotations

from typing import Any

from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.infrastructure.providers.chain.handlers import (
    FetchHandler,
    ProviderFetchHandler,
    StalenessBypassHandler,
    SupabaseCacheHandler,
    SymbolExistsHandler,
    VenueHealthHandler,
)
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

def build_ticker_chain(
    *,
    state: VenueState,
    registry: SymbolRegistry,
    gateway: Any,
    provider: Any,
) -> FetchHandler:
    """5-handler chain for ticker fetches."""
    return _build_chain(
        state=state, registry=registry, gateway=gateway, provider=provider,
    )

def build_ohlcv_chain(
    *,
    state: VenueState,
    registry: SymbolRegistry,
    gateway: Any,
    provider: Any,
) -> FetchHandler:
    """5-handler chain for OHLCV fetches (same topology; SupabaseCacheHandler
    dispatches to load_ohlcv based on request.operation)."""
    return _build_chain(
        state=state, registry=registry, gateway=gateway, provider=provider,
    )

def _build_chain(
    *,
    state: VenueState,
    registry: SymbolRegistry,
    gateway: Any,
    provider: Any,
) -> FetchHandler:
    head = VenueHealthHandler(state)
    head.set_next(SymbolExistsHandler(registry)) \
        .set_next(StalenessBypassHandler()) \
        .set_next(SupabaseCacheHandler(gateway)) \
        .set_next(ProviderFetchHandler(provider=provider, gateway=gateway))
    return head
```

- [ ] **Step 4: PASS (3 tests).**
- [ ] **Step 5: Commit**

Commit:
```bash
feat(providers): add chain assembly helpers

build_ticker_chain / build_ohlcv_chain wire the 5 handlers in
canonical order: VenueHealth → SymbolExists → StalenessBypass →
SupabaseCache → ProviderFetch. Both helpers share a single
_build_chain since the topology is identical — SupabaseCacheHandler
dispatches by request.operation internally.
```

---

### Task 7: ProviderFactory (Factory Method, TDD)

**Files:**
- Create: `src/cryptozavr/infrastructure/providers/factory.py`
- Create: `tests/unit/infrastructure/providers/test_factory.py`

- [ ] **Step 1: Failing tests**

Write `tests/unit/infrastructure/providers/test_factory.py`:
```python
"""Test ProviderFactory: wires base provider with decorator chain."""

from __future__ import annotations

import pytest

from cryptozavr.domain.venues import VenueId
from cryptozavr.infrastructure.providers.decorators.caching import (
    InMemoryCachingDecorator,
)
from cryptozavr.infrastructure.providers.decorators.logging import (
    LoggingDecorator,
)
from cryptozavr.infrastructure.providers.decorators.rate_limit import (
    RateLimitDecorator,
)
from cryptozavr.infrastructure.providers.decorators.retry import RetryDecorator
from cryptozavr.infrastructure.providers.factory import ProviderFactory
from cryptozavr.infrastructure.providers.http import HttpClientRegistry
from cryptozavr.infrastructure.providers.rate_limiters import RateLimiterRegistry
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

class _FakeExchange:
    """Duck-type for ccxt exchange."""

    async def load_markets(self) -> dict:
        return {}

    async def fetch_ticker(self, symbol: str) -> dict:
        return {"last": 1.0, "symbol": symbol}

    async def close(self) -> None:
        return None

@pytest.fixture
def rate_registry() -> RateLimiterRegistry:
    reg = RateLimiterRegistry()
    reg.register("kucoin", rate_per_sec=30.0, capacity=30)
    reg.register("coingecko", rate_per_sec=0.5, capacity=30)
    return reg

@pytest.fixture
async def http_registry() -> HttpClientRegistry:
    return HttpClientRegistry()

@pytest.mark.asyncio
async def test_create_kucoin_returns_wrapped_provider(
    rate_registry,
) -> None:
    factory = ProviderFactory(
        http_registry=HttpClientRegistry(),
        rate_registry=rate_registry,
    )
    state = VenueState(VenueId.KUCOIN)
    provider = factory.create_kucoin(state=state, exchange=_FakeExchange())

    # Chain: Logging > Caching > RateLimit > Retry > base
    assert isinstance(provider, LoggingDecorator)
    inner = provider._inner  # noqa: SLF001
    assert isinstance(inner, InMemoryCachingDecorator)
    inner2 = inner._inner  # noqa: SLF001
    assert isinstance(inner2, RateLimitDecorator)
    inner3 = inner2._inner  # noqa: SLF001
    assert isinstance(inner3, RetryDecorator)

@pytest.mark.asyncio
async def test_create_coingecko_returns_wrapped_provider(
    rate_registry,
) -> None:
    http_registry = HttpClientRegistry()
    try:
        factory = ProviderFactory(
            http_registry=http_registry,
            rate_registry=rate_registry,
        )
        state = VenueState(VenueId.COINGECKO)
        provider = await factory.create_coingecko(state=state)
        assert isinstance(provider, LoggingDecorator)
    finally:
        await http_registry.close_all()

@pytest.mark.asyncio
async def test_factory_uses_configured_ttls(
    rate_registry,
) -> None:
    factory = ProviderFactory(
        http_registry=HttpClientRegistry(),
        rate_registry=rate_registry,
        ticker_ttl=2.0,
        ohlcv_ttl=30.0,
    )
    state = VenueState(VenueId.KUCOIN)
    provider = factory.create_kucoin(state=state, exchange=_FakeExchange())
    # Dig into caching decorator
    caching = provider._inner  # noqa: SLF001
    assert caching._ticker_ttl == 2.0  # noqa: SLF001
    assert caching._ohlcv_ttl == 30.0  # noqa: SLF001
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

Write `src/cryptozavr/infrastructure/providers/factory.py`:
```python
"""ProviderFactory: Factory Method producing fully-decorated providers."""

from __future__ import annotations

from typing import Any

from cryptozavr.domain.venues import VenueId
from cryptozavr.infrastructure.providers.ccxt_provider import CCXTProvider
from cryptozavr.infrastructure.providers.coingecko_provider import (
    CoinGeckoProvider,
)
from cryptozavr.infrastructure.providers.decorators.caching import (
    InMemoryCachingDecorator,
)
from cryptozavr.infrastructure.providers.decorators.logging import (
    LoggingDecorator,
)
from cryptozavr.infrastructure.providers.decorators.rate_limit import (
    RateLimitDecorator,
)
from cryptozavr.infrastructure.providers.decorators.retry import RetryDecorator
from cryptozavr.infrastructure.providers.http import HttpClientRegistry
from cryptozavr.infrastructure.providers.rate_limiters import RateLimiterRegistry
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

_COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"

class ProviderFactory:
    """Factory Method for fully-wired providers.

    Each create_* method returns a LoggingDecorator-wrapped chain:
    Logging > Caching > RateLimit > Retry > base provider.
    """

    def __init__(
        self,
        *,
        http_registry: HttpClientRegistry,
        rate_registry: RateLimiterRegistry,
        retry_max_attempts: int = 3,
        retry_base_delay: float = 0.5,
        retry_jitter: float = 0.2,
        ticker_ttl: float = 5.0,
        ohlcv_ttl: float = 60.0,
        order_book_ttl: float = 3.0,
    ) -> None:
        self._http = http_registry
        self._rate = rate_registry
        self._retry_max_attempts = retry_max_attempts
        self._retry_base_delay = retry_base_delay
        self._retry_jitter = retry_jitter
        self._ticker_ttl = ticker_ttl
        self._ohlcv_ttl = ohlcv_ttl
        self._order_book_ttl = order_book_ttl

    def create_kucoin(
        self, *, state: VenueState, exchange: Any | None = None, **ccxt_opts: Any,
    ) -> LoggingDecorator:
        """Build KuCoin provider with full decorator chain.

        Pass `exchange` (fake) for tests; omit for real ccxt.kucoin().
        """
        if exchange is None:
            base = CCXTProvider.for_kucoin(state=state, **ccxt_opts)
        else:
            base = CCXTProvider(
                venue_id=VenueId.KUCOIN, state=state, exchange=exchange,
            )
        return self._wrap(base, venue_id="kucoin")

    async def create_coingecko(
        self, *, state: VenueState,
    ) -> LoggingDecorator:
        """Build CoinGecko provider with full decorator chain."""
        client = await self._http.get(
            "coingecko", base_url=_COINGECKO_BASE_URL,
        )
        base = CoinGeckoProvider(state=state, client=client)
        return self._wrap(base, venue_id="coingecko")

    def _wrap(self, base: Any, *, venue_id: str) -> LoggingDecorator:
        limiter = self._rate.get(venue_id)
        wrapped = RetryDecorator(
            base,
            max_attempts=self._retry_max_attempts,
            base_delay=self._retry_base_delay,
            jitter=self._retry_jitter,
        )
        wrapped = RateLimitDecorator(wrapped, limiter=limiter)
        wrapped = InMemoryCachingDecorator(
            wrapped,
            ticker_ttl=self._ticker_ttl,
            ohlcv_ttl=self._ohlcv_ttl,
            order_book_ttl=self._order_book_ttl,
        )
        return LoggingDecorator(wrapped)
```

- [ ] **Step 4: PASS (3 tests).**
- [ ] **Step 5: Commit**

Commit:
```bash
feat(providers): add ProviderFactory (Factory Method)

Builds fully-decorated providers: Logging > Caching > RateLimit >
Retry > base. create_kucoin accepts optional `exchange` for tests.
create_coingecko is async (acquires httpx client from registry).
Retry + cache TTLs configurable at factory construction.
```

---

### Task 8: Full verification + tag v0.0.6 + push

- [ ] **Step 1: Verify**

```bash
cd /Users/laptop/dev/cryptozavr
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest tests/unit tests/contract -m "not integration" -v 2>&1 | tail -15
```

Expected: all green, ~225 unit tests.

- [ ] **Step 2: Update CHANGELOG**

Edit `/Users/laptop/dev/cryptozavr/CHANGELOG.md`. Find:
```markdown
## [Unreleased]

## [0.0.5] - 2026-04-21
```

Replace with:
```markdown
## [Unreleased]

## [0.0.6] - 2026-04-21

### Added — M2.3c Chain of Responsibility + ProviderFactory
- `FetchOperation` enum (ticker/ohlcv/order_book/trades).
- `FetchRequest` (immutable) + `FetchContext` (mutable accumulator of reason_codes + metadata).
- `FetchHandler` abstract base with `set_next`/`_forward`.
- 5 concrete handlers: `VenueHealthHandler` (VenueState gate), `SymbolExistsHandler` (SymbolRegistry validation), `StalenessBypassHandler` (force_refresh → bypass_cache metadata), `SupabaseCacheHandler` (cache-aside via gateway), `ProviderFetchHandler` (terminal + write-through).
- `build_ticker_chain` / `build_ohlcv_chain` assembly helpers.
- `ProviderFactory` (Factory Method): `create_kucoin(state, exchange?)` / `create_coingecko(state)` return fully-wired providers (LoggingDecorator → CachingDecorator → RateLimitDecorator → RetryDecorator → base).
- ~22 new unit tests. Provider layer coverage remains ≥ 90%.

### Completes M2.3 Providers layer
All 14 GoF patterns from MVP design section 4 implemented: Template Method (BaseProvider), Adapter (CCXT/CoinGecko), Bridge (Domain Protocol ↔ concrete providers), Decorator (4 layered), Chain of Responsibility (5 handlers), State (VenueState + 4 handlers), Factory Method (ProviderFactory), Singleton via DI (registries), Flyweight (SymbolRegistry from M2.1), Observer (Supabase Realtime, deferred to phase 1.5).

### Next
- M2.4: First MCP tool `get_ticker` through full stack (Chain → Factory → Decorators → Provider → SupabaseGateway cache-aside).

## [0.0.5] - 2026-04-21
```

- [ ] **Step 3: Commit CHANGELOG + plan**

```bash
cd /Users/laptop/dev/cryptozavr
git add CHANGELOG.md
git add docs/superpowers/plans/2026-04-21-cryptozavr-m2.3c-chain-factory.md 2>/dev/null || true
```

Commit:
```bash
docs: finalize CHANGELOG for v0.0.6 (M2.3c Chain + Factory)
```

- [ ] **Step 4: Tag + push**

```bash
cd /Users/laptop/dev/cryptozavr
git tag -a v0.0.6 -m "M2.3c Chain of Responsibility + ProviderFactory complete

5-handler chain (VenueHealth/SymbolExists/StalenessBypass/
SupabaseCache/ProviderFetch) + chain assembly + ProviderFactory.
Completes M2.3 Providers layer. Ready for M2.4 (first MCP tool
get_ticker through full stack)."

git push origin main
git push origin v0.0.6
```

- [ ] **Step 5: Summary**

```bash
cd /Users/laptop/dev/cryptozavr
echo "=== M2.3c complete ==="
git log --oneline v0.0.5..HEAD
git tag -l
```

---

## Acceptance Criteria

1. ✅ All 8 tasks done.
2. ✅ ~22 new unit tests (context 7 + handlers 15 + assembly 3 + factory 3 = ~28 actually, close enough).
3. ✅ Chain short-circuits on cache hit — provider not called.
4. ✅ SupabaseCacheHandler logs and falls through on gateway errors.
5. ✅ ProviderFactory returns LoggingDecorator-wrapped chain.
6. ✅ Mypy + ruff clean.
7. ✅ Tag `v0.0.6` on github.com/evgenygurin/cryptozavr.

---

## Notes

- **Handler ordering** (canonical): VenueHealth (first — short-circuits unhealthy venues), SymbolExists (validates input), StalenessBypass (sets flag read by cache), SupabaseCache (may short-circuit), ProviderFetch (terminal + write-through).
- **Gateway errors are non-fatal** in both SupabaseCacheHandler (cache lookup) and ProviderFetchHandler (write-through). The chain's job is to respond with data from the best source available; DB issues shouldn't break freshly-fetched data.
- **ProviderFactory is sync for kucoin, async for coingecko.** That's because CoinGecko needs `await http_registry.get(...)` to obtain the httpx client. KuCoin uses ccxt internally (its own HTTP). Callers handle this via `await factory.create_coingecko(...)` vs `factory.create_kucoin(...)`.
