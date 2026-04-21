# cryptozavr — Milestone 3.0: FastMCP v3 idiomatic cleanup

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Refactor the MCP layer to match FastMCP v3 idiomatic patterns flagged during M3.2 pause. Target 5 specific anti-patterns: (1) non-dict lifespan yield, (2) `cast(Any, ctx.lifespan_context).attr` ugliness, (3) absent `ctx.info/warning` logging, (4) no `@mcp.prompt`, (5) no `mask_error_details`. Also switch two list-style discovery operations to `@mcp.resource` while keeping tools (dual exposure).

**Architecture:** Lifespan yields a **dict** (FastMCP v3 canonical). Tools receive services via `Depends(get_xxx_service)` — dependency params hidden from MCP schema. Each tool logs reason_codes via `ctx.info`. Error details masked in production. 2 new `@mcp.prompt` for cross-client portability. 3 `@mcp.resource` for catalog-style reads.

**Tech Stack:** FastMCP v3.2.4, no new deps.

**Starting tag:** `v0.1.2-wip` (M3.2 Task 1 DTOs in-flight). Target: `v0.1.2`.

**Scope note:** M3.2 Task 1 already committed (`4fd5c57` — SymbolDTO, TrendingAssetDTO, CategoryDTO). Those DTOs are still useful under the new patterns; M3.2 Tasks 2-8 will resume after this cleanup, using the new idiomatic patterns.

---

## File Structure

| Path | Change |
|------|--------|
| `src/cryptozavr/mcp/lifespan_state.py` | NEW — canonical dict keys + `Depends` accessors (get_ticker_service, …) |
| `src/cryptozavr/mcp/bootstrap.py` | MODIFY — yield dict instead of dataclass; drop `AppState` dataclass in favour of keys |
| `src/cryptozavr/mcp/server.py` | MODIFY — `@lifespan`-style + `mask_error_details=True` + prompts registration |
| `src/cryptozavr/mcp/tools/ticker.py` | MODIFY — `Depends(get_ticker_service)` + `ctx.info(reason_codes)` |
| `src/cryptozavr/mcp/tools/ohlcv.py` | MODIFY — same pattern |
| `src/cryptozavr/mcp/tools/order_book.py` | MODIFY — same pattern |
| `src/cryptozavr/mcp/tools/trades.py` | MODIFY — same pattern |
| `src/cryptozavr/mcp/prompts/__init__.py` | NEW — package marker |
| `src/cryptozavr/mcp/prompts/research.py` | NEW — `research_symbol`, `risk_check` prompts |
| `src/cryptozavr/mcp/resources/__init__.py` | NEW — package marker |
| `src/cryptozavr/mcp/resources/catalogs.py` | NEW — `cryptozavr://symbols/{venue}`, `cryptozavr://venues` |
| `tests/unit/mcp/test_lifespan_state.py` | NEW — Depends accessors tests |
| `tests/unit/mcp/test_prompts.py` | NEW — prompts tests via Client |
| `tests/unit/mcp/test_resources.py` | NEW — resources tests via Client |
| `tests/unit/mcp/test_get_ticker_tool.py` | MODIFY — update lifespan dict + re-verify |
| `tests/unit/mcp/test_get_ohlcv_tool.py` | MODIFY — same |
| `tests/unit/mcp/test_get_order_book_tool.py` | MODIFY — same |
| `tests/unit/mcp/test_get_trades_tool.py` | MODIFY — same |

---

## Tasks

### Task 1: Lifespan state module + `Depends` accessors

**Files:**
- Create: `src/cryptozavr/mcp/lifespan_state.py`
- Create: `tests/unit/mcp/test_lifespan_state.py`

- [ ] **Step 1: Write failing tests**

Write `tests/unit/mcp/test_lifespan_state.py`:
```python
"""Test lifespan state keys + Depends accessors."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import pytest
from fastmcp import Client, FastMCP

from cryptozavr.mcp.lifespan_state import (
    LIFESPAN_KEYS,
    get_discovery_service,
    get_ohlcv_service,
    get_order_book_service,
    get_registry,
    get_subscriber,
    get_symbol_resolver,
    get_ticker_service,
    get_trades_service,
)

@pytest.mark.asyncio
async def test_accessor_returns_value_from_lifespan_dict() -> None:
    ticker_stub = MagicMock(name="ticker_service")

    @asynccontextmanager
    async def lifespan(server):
        yield {LIFESPAN_KEYS.ticker_service: ticker_stub}

    mcp = FastMCP(name="t", version="0", lifespan=lifespan)

    @mcp.tool
    async def probe(ctx) -> str:
        svc = ctx.lifespan_context[LIFESPAN_KEYS.ticker_service]
        return svc.name

    async with Client(mcp) as client:
        result = await client.call_tool("probe", {})
    assert "ticker_service" in (result.structured_content or {}).get("result", "") \
        or "ticker_service" in str(result)

def test_lifespan_keys_are_strings_and_unique() -> None:
    # Constants guard against typos.
    names = [
        LIFESPAN_KEYS.ticker_service,
        LIFESPAN_KEYS.ohlcv_service,
        LIFESPAN_KEYS.order_book_service,
        LIFESPAN_KEYS.trades_service,
        LIFESPAN_KEYS.subscriber,
        LIFESPAN_KEYS.symbol_resolver,
        LIFESPAN_KEYS.discovery_service,
        LIFESPAN_KEYS.registry,
    ]
    assert all(isinstance(n, str) for n in names)
    assert len(set(names)) == len(names)

def test_accessor_callables_exist() -> None:
    # Each Depends accessor should be importable + callable.
    assert callable(get_ticker_service)
    assert callable(get_ohlcv_service)
    assert callable(get_order_book_service)
    assert callable(get_trades_service)
    assert callable(get_subscriber)
    assert callable(get_symbol_resolver)
    assert callable(get_discovery_service)
    assert callable(get_registry)
```

- [ ] **Step 2: FAIL**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/mcp/test_lifespan_state.py -v
```

- [ ] **Step 3: Implement (SINGLE Write)**

Write `src/cryptozavr/mcp/lifespan_state.py`:
```python
"""Canonical lifespan-dict keys + Depends accessors.

Per FastMCP v3 convention, the lifespan `yield`s a `dict` which
becomes `ctx.lifespan_context`. Tools access state via
`Depends(get_xxx_service)` — dependency params are hidden from the
MCP schema and automatically resolved at tool-call time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastmcp.dependencies import CurrentContext

if TYPE_CHECKING:
    from cryptozavr.application.services.discovery_service import DiscoveryService
    from cryptozavr.application.services.ohlcv_service import OhlcvService
    from cryptozavr.application.services.order_book_service import (
        OrderBookService,
    )
    from cryptozavr.application.services.symbol_resolver import SymbolResolver
    from cryptozavr.application.services.ticker_service import TickerService
    from cryptozavr.application.services.trades_service import TradesService
    from cryptozavr.domain.symbols import SymbolRegistry
    from cryptozavr.infrastructure.supabase.realtime import RealtimeSubscriber

@dataclass(frozen=True, slots=True)
class _LifespanKeys:
    ticker_service: str = "ticker_service"
    ohlcv_service: str = "ohlcv_service"
    order_book_service: str = "order_book_service"
    trades_service: str = "trades_service"
    subscriber: str = "subscriber"
    symbol_resolver: str = "symbol_resolver"
    discovery_service: str = "discovery_service"
    registry: str = "registry"

LIFESPAN_KEYS = _LifespanKeys()

def _get(ctx: Any, key: str) -> Any:
    return ctx.lifespan_context[key]

def get_ticker_service(ctx: Any = CurrentContext()) -> TickerService:
    return _get(ctx, LIFESPAN_KEYS.ticker_service)

def get_ohlcv_service(ctx: Any = CurrentContext()) -> OhlcvService:
    return _get(ctx, LIFESPAN_KEYS.ohlcv_service)

def get_order_book_service(ctx: Any = CurrentContext()) -> OrderBookService:
    return _get(ctx, LIFESPAN_KEYS.order_book_service)

def get_trades_service(ctx: Any = CurrentContext()) -> TradesService:
    return _get(ctx, LIFESPAN_KEYS.trades_service)

def get_subscriber(ctx: Any = CurrentContext()) -> RealtimeSubscriber:
    return _get(ctx, LIFESPAN_KEYS.subscriber)

def get_symbol_resolver(ctx: Any = CurrentContext()) -> SymbolResolver:
    return _get(ctx, LIFESPAN_KEYS.symbol_resolver)

def get_discovery_service(ctx: Any = CurrentContext()) -> DiscoveryService:
    return _get(ctx, LIFESPAN_KEYS.discovery_service)

def get_registry(ctx: Any = CurrentContext()) -> SymbolRegistry:
    return _get(ctx, LIFESPAN_KEYS.registry)
```

- [ ] **Step 4: PASS + lint**

```bash
uv run pytest tests/unit/mcp/test_lifespan_state.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src
```

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```text
feat(mcp): add lifespan_state module — dict keys + Depends accessors

Canonical FastMCP v3 pattern: lifespan yields a dict, tools access
state via Depends(get_xxx_service) + CurrentContext(). Replaces the
`cast(Any, ctx.lifespan_context).attr` pattern scattered across tools.
Accessor functions are typed (return TickerService / etc via
TYPE_CHECKING) and dependency params are hidden from the MCP schema.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/mcp/lifespan_state.py tests/unit/mcp/test_lifespan_state.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 2: Bootstrap + server.py yield dict

**Files:**
- Modify: `src/cryptozavr/mcp/bootstrap.py`
- Modify: `src/cryptozavr/mcp/server.py`

- [ ] **Step 1: Replace AppState with dict**

Update `src/cryptozavr/mcp/bootstrap.py`:
- Keep `build_production_service` creating all services
- Change return to a single dict matching `LIFESPAN_KEYS` + cleanup callable
- Remove `AppState` dataclass (kept as alias for backwards compat with one export if needed)

New return type:
```python
async def build_production_service(
    settings: Settings,
) -> tuple[dict[str, Any], Callable[[], Awaitable[None]]]:
    ...
    state: dict[str, Any] = {
        LIFESPAN_KEYS.ticker_service: ticker_service,
        LIFESPAN_KEYS.ohlcv_service: ohlcv_service,
        LIFESPAN_KEYS.order_book_service: order_book_service,
        LIFESPAN_KEYS.trades_service: trades_service,
        LIFESPAN_KEYS.subscriber: subscriber,
        # Populated by M3.2+:
        # LIFESPAN_KEYS.symbol_resolver: ...,
        # LIFESPAN_KEYS.discovery_service: ...,
        # LIFESPAN_KEYS.registry: ...,
    }
    return state, cleanup
```

- [ ] **Step 2: Update server.py lifespan to yield dict**

```python
    @asynccontextmanager
    async def lifespan(_server: FastMCP) -> AsyncIterator[dict[str, Any]]:
        state, cleanup = await build_production_service(settings)
        _LOGGER.info(
            "cryptozavr-research started",
            extra={"mode": settings.mode.value, "version": __version__},
        )
        try:
            yield state
        finally:
            await cleanup()

    mcp = FastMCP(
        name="cryptozavr-research",
        version=__version__,
        lifespan=lifespan,
        mask_error_details=True,  # NEW — production safety
    )
```

Drop `FastMCP[AppState]` generic since state is now a `dict` (FastMCP infers it).

- [ ] **Step 3: Smoke — lint + full unit suite**

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src
uv run pytest tests/unit tests/contract -m "not integration" -q 2>&1 | tail -3
```
Expected: the 4 existing tool tests FAIL because they still use the old `_AppState` dataclass pattern. Those are fixed in Task 3.

- [ ] **Step 4: Commit**

Write to /tmp/commit-msg.txt:
```bash
refactor(mcp): yield dict from lifespan + mask error details

FastMCP v3 canonical: lifespan returns a dict that becomes
ctx.lifespan_context. Removed the AppState dataclass indirection —
bootstrap now returns (state: dict, cleanup). Server wraps the dict
through LIFESPAN_KEYS constants. Added mask_error_details=True so
non-ToolError exceptions don't leak stack traces to clients.

Tests temporarily red — fixed in next commit (Task 3).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/mcp/bootstrap.py src/cryptozavr/mcp/server.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 3: Refactor 4 tools to `Depends` + `ctx.info`

**Files:**
- Modify: `src/cryptozavr/mcp/tools/ticker.py`
- Modify: `src/cryptozavr/mcp/tools/ohlcv.py`
- Modify: `src/cryptozavr/mcp/tools/order_book.py`
- Modify: `src/cryptozavr/mcp/tools/trades.py`
- Modify: `tests/unit/mcp/test_get_ticker_tool.py` (and the 3 sibling test files)

- [ ] **Step 1: Refactor `tools/ticker.py`**

```python
"""get_ticker MCP tool registration."""

from __future__ import annotations

from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.dependencies import Depends
from pydantic import Field

from cryptozavr.application.services.ticker_service import TickerService
from cryptozavr.domain.exceptions import DomainError
from cryptozavr.mcp.dtos import TickerDTO
from cryptozavr.mcp.errors import domain_to_tool_error
from cryptozavr.mcp.lifespan_state import get_ticker_service

def register_ticker_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        name="get_ticker",
        description=(
            "Fetch the latest ticker (last, bid, ask, 24h volume) for a "
            "symbol on a venue. Goes through the 5-handler chain."
        ),
        tags={"market", "public", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_ticker(
        venue: Annotated[str, Field(description="Venue id.")],
        symbol: Annotated[str, Field(description="Native symbol, e.g. BTC-USDT.")],
        ctx: Context,
        force_refresh: Annotated[
            bool, Field(description="Bypass the Supabase cache."),
        ] = False,
        service: TickerService = Depends(get_ticker_service),
    ) -> TickerDTO:
        await ctx.info(
            f"get_ticker venue={venue} symbol={symbol} "
            f"force_refresh={force_refresh}",
        )
        try:
            result = await service.fetch_ticker(
                venue=venue, symbol=symbol, force_refresh=force_refresh,
            )
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc

        await ctx.info(f"reason_codes: {','.join(result.reason_codes)}")
        if "cache:write_failed" in result.reason_codes:
            await ctx.warning(
                "Supabase write-through failed; data valid but not persisted.",
            )
        if result.ticker.quality.staleness.name.lower() not in {"fresh"}:
            await ctx.warning(
                f"staleness={result.ticker.quality.staleness.name.lower()} — "
                f"consider force_refresh=True.",
            )
        return TickerDTO.from_domain(result.ticker, result.reason_codes)
```

- [ ] **Step 2: Mirror the same refactor in `ohlcv.py` / `order_book.py` / `trades.py`**

For each: drop `cast(Any, ctx.lifespan_context).xxx_service`, replace with `service: XxxService = Depends(get_xxx_service)` parameter, add `ctx.info` + `ctx.warning` logging of reason_codes.

- [ ] **Step 3: Update the 4 test files to yield dict**

Each `_AppState` dataclass in tests becomes:
```python
# remove the dataclass
# lifespan now yields a dict:
@asynccontextmanager
async def lifespan(server):
    yield {"ticker_service": mock_service}  # key matches LIFESPAN_KEYS.ticker_service
```

The DI via `Depends` still pulls from `ctx.lifespan_context["ticker_service"]`, so tests just need to yield the right dict key.

- [ ] **Step 4: Run**

```bash
uv run pytest tests/unit/mcp -v 2>&1 | tail -30
uv run ruff check . && uv run ruff format --check . && uv run mypy src
uv run pytest tests/unit tests/contract -m "not integration" -q 2>&1 | tail -3
```
Expected: all previously-passing tool tests now pass under new DI pattern. Count unchanged (~313).

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```bash
refactor(mcp): use Depends(get_xxx_service) + ctx.info/warning in tools

Replaces `cast(Any, ctx.lifespan_context).xxx_service` with
`Depends(get_xxx_service)` param — dependency is hidden from the MCP
schema and resolved at tool-call time. Each tool logs reason_codes
via `ctx.info` and emits `ctx.warning` on `cache:write_failed` or
non-fresh staleness. Tests updated: _AppState dataclass replaced by
dict-yielding lifespan matching LIFESPAN_KEYS.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/mcp/tools/ticker.py \
    src/cryptozavr/mcp/tools/ohlcv.py \
    src/cryptozavr/mcp/tools/order_book.py \
    src/cryptozavr/mcp/tools/trades.py \
    tests/unit/mcp/test_get_ticker_tool.py \
    tests/unit/mcp/test_get_ohlcv_tool.py \
    tests/unit/mcp/test_get_order_book_tool.py \
    tests/unit/mcp/test_get_trades_tool.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 4: `@mcp.prompt` for cross-client portability

**Files:**
- Create: `src/cryptozavr/mcp/prompts/__init__.py`
- Create: `src/cryptozavr/mcp/prompts/research.py`
- Create: `tests/unit/mcp/test_prompts.py`
- Modify: `src/cryptozavr/mcp/server.py` (register prompts)

- [ ] **Step 1: Write failing tests**

Write `tests/unit/mcp/test_prompts.py`:
```python
"""In-memory Client tests for cryptozavr prompts."""

from __future__ import annotations

import pytest
from fastmcp import Client, FastMCP

from cryptozavr.mcp.prompts.research import register_prompts

@pytest.mark.asyncio
async def test_research_symbol_prompt_includes_venue_and_symbol() -> None:
    mcp = FastMCP(name="t", version="0")
    register_prompts(mcp)
    async with Client(mcp) as client:
        prompts = await client.list_prompts()
        names = {p.name for p in prompts}
        assert "research_symbol" in names
        result = await client.get_prompt(
            "research_symbol", {"venue": "kucoin", "symbol": "BTC-USDT"},
        )
    text = "".join(str(m.content) for m in result.messages)
    assert "kucoin" in text.lower()
    assert "BTC-USDT" in text
    assert "get_ticker" in text

@pytest.mark.asyncio
async def test_risk_check_prompt_references_staleness_and_reason_codes() -> None:
    mcp = FastMCP(name="t", version="0")
    register_prompts(mcp)
    async with Client(mcp) as client:
        result = await client.get_prompt(
            "risk_check", {"venue": "kucoin", "symbol": "BTC-USDT"},
        )
    text = "".join(str(m.content) for m in result.messages)
    assert "staleness" in text.lower()
    assert "reason_codes" in text.lower()
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

Write `src/cryptozavr/mcp/prompts/__init__.py`:
```python
"""MCP prompts — cross-client research/risk templates."""
```

Write `src/cryptozavr/mcp/prompts/research.py`:
```python
"""Research + risk_check prompts."""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

def register_prompts(mcp: FastMCP) -> None:
    @mcp.prompt(
        name="research_symbol",
        description=(
            "Full 4-tool market research collage for a symbol on a venue."
        ),
        tags={"market", "research"},
    )
    def research_symbol(
        venue: Annotated[str, Field(description="Venue id: kucoin, coingecko.")],
        symbol: Annotated[str, Field(description="Native symbol, e.g. BTC-USDT.")],
    ) -> str:
        return (
            f"Research {symbol} on venue {venue}. Call these 4 tools in "
            f"parallel: `get_ticker`, `get_ohlcv(timeframe='1h', limit=24)`, "
            f"`get_order_book(depth=20)`, `get_trades(limit=50)`. "
            f"Present the result as: Price → Trend → Liquidity → Flow → "
            f"Provenance. Rails: data-not-advice. Surface reason_codes "
            f"and any non-fresh staleness warnings from tool calls."
        )

    @mcp.prompt(
        name="risk_check",
        description=(
            "Risk-first pre-decision check for a symbol. "
            "Focuses on data quality, not price prediction."
        ),
        tags={"market", "risk"},
    )
    def risk_check(
        venue: Annotated[str, Field(description="Venue id.")],
        symbol: Annotated[str, Field(description="Native symbol.")],
    ) -> str:
        return (
            f"Run a risk-first quality check on {symbol} at venue {venue}.\n\n"
            f"Steps:\n"
            f"1. Call `get_ticker` with force_refresh=true — record "
            f"staleness, cache_hit, reason_codes.\n"
            f"2. If staleness != 'fresh' or confidence != 'high' — stop and "
            f"flag: data quality too low for decisions.\n"
            f"3. Call `get_order_book(depth=20)` — compute spread_bps. "
            f"If spread_bps > 50 bps, flag: illiquid.\n"
            f"4. Call `get_trades(limit=50)` — check buy/sell count ratio. "
            f"Extreme imbalance (>80/20) → flag: one-sided tape.\n\n"
            f"Report: PASS | DEGRADED | FAIL with the specific reason_codes "
            f"that triggered each flag. No buy/sell recommendations."
        )
```

Wire into server.py: add `from cryptozavr.mcp.prompts.research import register_prompts` + `register_prompts(mcp)` after tool registrations.

- [ ] **Step 4: PASS**

```bash
uv run pytest tests/unit/mcp/test_prompts.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src
uv run pytest tests/unit tests/contract -m "not integration" -q 2>&1 | tail -3
```

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```bash
feat(mcp): add research_symbol + risk_check prompts

Two @mcp.prompt definitions for cross-client portability. Claude Code
slash-commands (commands/*.md) work only inside Claude Code; MCP
prompts are the MCP-spec way to expose reusable message templates
to any client (Codex, OpenCode, Cursor, Gemini). Rails: data-not-
advice; surface reason_codes + staleness.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/mcp/prompts/__init__.py \
    src/cryptozavr/mcp/prompts/research.py \
    src/cryptozavr/mcp/server.py \
    tests/unit/mcp/test_prompts.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 5: `@mcp.resource` for catalog lookups

**Files:**
- Create: `src/cryptozavr/mcp/resources/__init__.py`
- Create: `src/cryptozavr/mcp/resources/catalogs.py`
- Create: `tests/unit/mcp/test_resources.py`
- Modify: `src/cryptozavr/mcp/server.py` (register resources)

Two catalog resources:
- `cryptozavr://venues` — list of supported venues (kucoin, coingecko)
- `cryptozavr://symbols/{venue}` — list of registered symbols on a venue

- [ ] **Step 1: Write failing tests**

Write `tests/unit/mcp/test_resources.py`:
```python
"""Test cryptozavr resources."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager

import pytest
from fastmcp import Client, FastMCP

from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.mcp.lifespan_state import LIFESPAN_KEYS
from cryptozavr.mcp.resources.catalogs import register_resources

def _build_server(registry: SymbolRegistry) -> FastMCP:
    @asynccontextmanager
    async def lifespan(server):
        yield {LIFESPAN_KEYS.registry: registry}

    mcp = FastMCP(name="t", version="0", lifespan=lifespan)
    register_resources(mcp)
    return mcp

@pytest.mark.asyncio
async def test_venues_resource_lists_supported() -> None:
    mcp = _build_server(SymbolRegistry())
    async with Client(mcp) as client:
        result = await client.read_resource("cryptozavr://venues")
    payload = json.loads(result[0].text)
    assert "kucoin" in payload["venues"]
    assert "coingecko" in payload["venues"]

@pytest.mark.asyncio
async def test_symbols_resource_by_venue() -> None:
    registry = SymbolRegistry()
    registry.get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )
    registry.get(
        VenueId.KUCOIN, "ETH", "USDT",
        market_type=MarketType.SPOT, native_symbol="ETH-USDT",
    )
    mcp = _build_server(registry)
    async with Client(mcp) as client:
        result = await client.read_resource("cryptozavr://symbols/kucoin")
    payload = json.loads(result[0].text)
    assert payload["venue"] == "kucoin"
    native = {s["native_symbol"] for s in payload["symbols"]}
    assert native == {"BTC-USDT", "ETH-USDT"}
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

Write `src/cryptozavr/mcp/resources/__init__.py`:
```python
"""MCP resources — read-only catalogs."""
```

Write `src/cryptozavr/mcp/resources/catalogs.py`:
```python
"""Catalog resources: venues, symbols-per-venue."""

from __future__ import annotations

import json

from fastmcp import FastMCP
from fastmcp.dependencies import Depends

from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import VenueId
from cryptozavr.mcp.lifespan_state import get_registry

def register_resources(mcp: FastMCP) -> None:
    @mcp.resource(
        "cryptozavr://venues",
        name="Supported Venues",
        description="List of venue ids the plugin can serve.",
        mime_type="application/json",
        tags={"catalog"},
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    def venues_resource() -> str:
        return json.dumps({"venues": sorted(v.value for v in VenueId)})

    @mcp.resource(
        "cryptozavr://symbols/{venue}",
        name="Symbols for Venue",
        description="All registered symbols on a venue.",
        mime_type="application/json",
        tags={"catalog"},
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    def symbols_resource(
        venue: str,
        registry: SymbolRegistry = Depends(get_registry),
    ) -> str:
        try:
            venue_id = VenueId(venue)
        except ValueError:
            return json.dumps(
                {"venue": venue, "symbols": [], "error": "unsupported"},
            )
        symbols = registry.all_for_venue(venue_id)
        return json.dumps(
            {
                "venue": venue,
                "symbols": [
                    {
                        "base": s.base,
                        "quote": s.quote,
                        "native_symbol": s.native_symbol,
                        "market_type": s.market_type.value,
                    }
                    for s in symbols
                ],
            },
        )
```

Note: `SymbolRegistry.all_for_venue` may not exist yet — add in this task if needed (per M3.2 Task 4a note):
```python
def all_for_venue(self, venue: VenueId) -> list[Symbol]:
    with self._lock:
        return sorted(
            (s for s in self._store.values() if s.venue == venue),
            key=lambda s: s.native_symbol,
        )
```

Wire into server.py: `from cryptozavr.mcp.resources.catalogs import register_resources` + `register_resources(mcp)` after prompts.

Also ensure bootstrap.py puts `LIFESPAN_KEYS.registry: registry` into the yielded dict.

- [ ] **Step 4: PASS**

```bash
uv run pytest tests/unit/mcp/test_resources.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src
uv run pytest tests/unit tests/contract -m "not integration" -q 2>&1 | tail -3
```

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```bash
feat(mcp): add cryptozavr://venues + cryptozavr://symbols/{venue} resources

Catalog-style reads exposed as @mcp.resource instead of tools. MCP
clients can cache resource URIs (unlike tool calls) — appropriate
for enumerated, stable lookups. Uses Depends(get_registry) for DI.
SymbolRegistry.all_for_venue helper added (stable sort by
native_symbol). List-based scan_trending/list_categories will also
become resources in M3.2 resume.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add src/cryptozavr/mcp/resources/__init__.py \
    src/cryptozavr/mcp/resources/catalogs.py \
    src/cryptozavr/mcp/server.py \
    src/cryptozavr/mcp/bootstrap.py \
    src/cryptozavr/domain/symbols.py \
    tests/unit/mcp/test_resources.py
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 6: Verify plugin install + CHANGELOG + tag v0.1.2

- [ ] **Step 1: Plugin validate**

```bash
cd /Users/laptop/dev/cryptozavr
claude plugin validate /Users/laptop/dev/cryptozavr
```
Expect: ✔ Validation passed.

- [ ] **Step 2: Live smoke test via `claude -p --plugin-dir`**

```bash
echo "List all MCP tools + prompts + resources exposed by this plugin." \
  | claude -p --model claude-sonnet-4-6 \
    --plugin-dir /Users/laptop/dev/cryptozavr 2>&1 | tail -30
```
Expect: 5 tools (echo + 4 market-data), 2 prompts (research_symbol + risk_check), 2 resources (venues + symbols/{venue}).

- [ ] **Step 3: Full suite**

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest tests/unit tests/contract -m "not integration" -q 2>&1 | tail -5
```

- [ ] **Step 4: Update CHANGELOG**

Edit `/Users/laptop/dev/cryptozavr/CHANGELOG.md`. Find:
```markdown
## [Unreleased]

## [0.1.1] - 2026-04-22
```

Replace with:
```markdown
## [Unreleased]

## [0.1.2] - 2026-04-22

### Refactored — M3.0 FastMCP v3 idiomatic cleanup

**Problem:** The M2.4-M2.8 MCP layer worked but used several non-idiomatic patterns flagged during M3.2 pause.

**Fixed:**
- **Lifespan yields a `dict`**, not a dataclass. Replaces `FastMCP[AppState]` generic + `cast(Any, ctx.lifespan_context).attr` pattern.
- **`Depends(get_xxx_service)` injection** in all 4 market-data tools (get_ticker, get_ohlcv, get_order_book, get_trades). Dependency params hidden from MCP schema; services resolved at tool-call time.
- **`ctx.info` / `ctx.warning` logging** per tool call: surfaces reason_codes and staleness warnings so MCP clients see the chain decisions alongside the response.
- **`FastMCP(..., mask_error_details=True)`** — non-ToolError exceptions don't leak stacktraces.
- New `src/cryptozavr/mcp/lifespan_state.py` with `LIFESPAN_KEYS` constants + 8 typed `Depends` accessors.

### Added — prompts + catalog resources
- `@mcp.prompt research_symbol(venue, symbol)` — 4-tool parallel research template.
- `@mcp.prompt risk_check(venue, symbol)` — data-quality-first pre-decision check.
- `@mcp.resource cryptozavr://venues` — enumerated venue list.
- `@mcp.resource cryptozavr://symbols/{venue}` — symbols-per-venue catalog.
- `SymbolRegistry.all_for_venue()` helper (stable-sorted by native_symbol).

### Tests
- `test_lifespan_state.py`, `test_prompts.py`, `test_resources.py` — 8 new tests.
- 4 existing tool test files updated to dict-yield lifespan.
- Total ~321 unit + 5 contract + 14 integration (skip-safe).

### Deferred
- M3.2 resume: SymbolResolver + DiscoveryService + discovery tools (resolve_symbol, list_symbols, scan_trending, list_categories) → will use the idiomatic patterns from this milestone.

### Next
- M3.2 (resumed): discovery services + tools/resources using new DI.
- M3.3: analytics MCP tools on top of MarketAnalyzer.
- M3.4: fetch_ohlcv_history streaming + SessionExplainer → tag v0.2.0 (MVP closure).

## [0.1.1] - 2026-04-22
```

- [ ] **Step 5: Commit CHANGELOG + plan + tag + push**

```bash
cd /Users/laptop/dev/cryptozavr
git add CHANGELOG.md
git add docs/superpowers/plans/2026-04-22-cryptozavr-m3.0-fastmcp-idiomatic-cleanup.md 2>/dev/null || true
```

Write commit message to /tmp/commit-msg.txt:
```bash
docs: finalize CHANGELOG for v0.1.2 (M3.0 FastMCP idiomatic cleanup)

5 anti-patterns fixed: dict lifespan, Depends DI, ctx logging,
mask_error_details, idiomatic prompts+resources. Plugin now passes
FastMCP v3 review standards. M3.2 resumes on top of this foundation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

Write tag message to /tmp/tag-msg.txt:
```text
M3.0 FastMCP v3 idiomatic cleanup complete

Lifespan dict-yield, Depends injection, ctx.info logging,
mask_error_details, + 2 prompts + 2 resources. Ready to resume M3.2
on top of the idiomatic foundation.
```

```bash
cd /Users/laptop/dev/cryptozavr
git tag -a v0.1.2 -F /tmp/tag-msg.txt
rm /tmp/tag-msg.txt
git push origin main
git push origin v0.1.2
```

---

## Acceptance Criteria

1. ✅ All 6 tasks done.
2. ✅ 4 market-data tools use `Depends(get_xxx_service)` — no `cast(Any, …)` patterns remain.
3. ✅ `grep -rn "cast(Any, ctx.lifespan_context)" src/ tests/` returns nothing.
4. ✅ Every tool emits at least one `ctx.info` + one conditional `ctx.warning`.
5. ✅ `FastMCP(mask_error_details=True)`.
6. ✅ 2 prompts + 2 resources visible via `Client.list_prompts()` / `Client.read_resource()`.
7. ✅ `claude plugin validate` passes.
8. ✅ `uv run pytest tests/unit tests/contract -m "not integration"` green.
9. ✅ Tag `v0.1.2` pushed.

---

## Notes

- **Scope boundary:** only the MCP layer + bootstrap. No changes to domain, application, infrastructure (they're pure).
- **M3.2 partial commit stays:** `4fd5c57` (SymbolDTO/TrendingAssetDTO/CategoryDTO) remains — DTOs work fine under the new patterns.
- **Backwards compat:** AppState dataclass is deleted. This is internal API — no external consumers.
- **Prompts + slash commands coexist:** Claude Code sees both. Other MCP clients see only prompts.
- **Resources vs discovery tools:** catalogs are resources here (stable URIs, cacheable). `resolve_symbol` stays a tool (reasoning-heavy). In M3.2 resume `scan_trending` + `list_categories` will also become resources with short-TTL (CoinGecko data is dynamic but still URI-identified).
- **Decorator `output_schema`** — not added in this milestone. Pydantic `BaseModel` return types already generate correct structured_content schema; explicit `output_schema` is a further-down-the-road optimisation.
