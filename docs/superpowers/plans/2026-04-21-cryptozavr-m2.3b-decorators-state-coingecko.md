# cryptozavr — Milestone 2.3b: Decorators + State + CoinGecko Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Расширить Providers layer: добавить CoinGeckoProvider (httpx-based), 4 composable Decorators (Retry/RateLimit/Caching/Logging), полный State pattern для VenueState с 4 handler-классами и автоматическими переходами. После M2.3b: `LoggingDecorator(CachingDecorator(RateLimitDecorator(RetryDecorator(provider))))` работает; VenueState транзитится Healthy→Degraded→Healthy→RateLimited→Healthy; CoinGecko `/simple/price` доступен через respx-mocked HTTP.

**Architecture:** Infrastructure L2 расширение. Decorators реализуют Decorator pattern вокруг `MarketDataProvider` Protocol (из Domain). State pattern: `VenueState` контекст делегирует `on_request_*` текущему `StateHandler` (HealthyStateHandler/DegradedStateHandler/RateLimitedStateHandler/DownStateHandler). CoinGecko использует `HttpClientRegistry` (из M2.3a) + httpx вместо ccxt.

**Tech Stack:** Python 3.12, httpx>=0.27, respx>=0.21 (HTTP mocking), freezegun>=1.5 (TTL testing), structlog>=24.4 (logging). Всё уже установлено в M2.3a.

**Milestone position:** M2.3b of 3 sub-milestones of M2.3.

**Spec reference:** `docs/superpowers/specs/2026-04-21-cryptozavr-mvp-design.md` section 4.
**Prior plans:** M1 (v0.0.1), M2.1 (v0.0.2), M2.2 (v0.0.3), M2.3a (v0.0.4).
**Starting tag:** `v0.0.4`. Target: `v0.0.5`.

---

## File Structure

### New files

| Path | Responsibility |
|------|---------------|
| `src/cryptozavr/infrastructure/providers/adapters/coingecko_adapter.py` | Pure functions: `simple_price_to_ticker`, `trending_to_assets`, `categories_to_list` |
| `src/cryptozavr/infrastructure/providers/coingecko_provider.py` | CoinGeckoProvider concrete (httpx + HttpClientRegistry) |
| `src/cryptozavr/infrastructure/providers/state/handlers.py` | 4 state handler classes |
| `src/cryptozavr/infrastructure/providers/decorators/__init__.py` | Package marker |
| `src/cryptozavr/infrastructure/providers/decorators/retry.py` | `RetryDecorator` |
| `src/cryptozavr/infrastructure/providers/decorators/rate_limit.py` | `RateLimitDecorator` |
| `src/cryptozavr/infrastructure/providers/decorators/caching.py` | `InMemoryCachingDecorator` + `Clock` Protocol |
| `src/cryptozavr/infrastructure/providers/decorators/logging.py` | `LoggingDecorator` |
| `tests/contract/fixtures/coingecko/trending.json` | CoinGecko `/search/trending` sample |
| `tests/contract/fixtures/coingecko/categories.json` | CoinGecko `/coins/categories` sample |
| `tests/contract/fixtures/coingecko/simple_price_btc.json` | CoinGecko `/simple/price?ids=bitcoin` sample |
| `tests/unit/infrastructure/providers/adapters/test_coingecko_adapter.py` | Adapter tests on fixtures |
| `tests/unit/infrastructure/providers/test_coingecko_provider.py` | Provider tests with respx |
| `tests/contract/test_coingecko_provider_contract.py` | End-to-end via fixtures |
| `tests/unit/infrastructure/providers/state/test_handlers.py` | Per-handler behaviour tests |
| `tests/unit/infrastructure/providers/decorators/__init__.py` | Package marker |
| `tests/unit/infrastructure/providers/decorators/test_retry_decorator.py` | Retry tests |
| `tests/unit/infrastructure/providers/decorators/test_rate_limit_decorator.py` | RateLimit tests |
| `tests/unit/infrastructure/providers/decorators/test_caching_decorator.py` | Caching tests (freezegun) |
| `tests/unit/infrastructure/providers/decorators/test_logging_decorator.py` | Logging tests |
| `tests/unit/infrastructure/providers/decorators/test_decorator_chain.py` | Composability integration test |

### Modified files

| Path | Change |
|------|--------|
| `src/cryptozavr/infrastructure/providers/state/venue_state.py` | Replace minimal context with full State pattern + delegation |
| `tests/unit/infrastructure/providers/state/test_venue_state.py` | Add transition tests |

---

## Tasks

### Task 1: CoinGecko fixtures + CoinGeckoAdapter (TDD)

**Files:**
- Create: fixtures (3 JSON files)
- Create: `src/cryptozavr/infrastructure/providers/adapters/coingecko_adapter.py`
- Create: `tests/unit/infrastructure/providers/adapters/test_coingecko_adapter.py`

- [ ] **Step 1: Write 3 fixture files**

Write to `/Users/laptop/dev/cryptozavr/tests/contract/fixtures/coingecko/simple_price_btc.json`:
```json
{
  "bitcoin": {
    "usd": 65000.5,
    "usd_24h_vol": 45230000000.0,
    "usd_24h_change": 2.5,
    "last_updated_at": 1745200800
  }
}
```

Write to `/Users/laptop/dev/cryptozavr/tests/contract/fixtures/coingecko/trending.json`:
```json
{
  "coins": [
    {"item": {"id": "bitcoin", "coin_id": 1, "name": "Bitcoin", "symbol": "BTC", "market_cap_rank": 1, "thumb": "btc.png", "small": "btc-s.png", "large": "btc-l.png", "slug": "bitcoin", "price_btc": 1.0, "score": 0}},
    {"item": {"id": "ethereum", "coin_id": 279, "name": "Ethereum", "symbol": "ETH", "market_cap_rank": 2, "thumb": "eth.png", "small": "eth-s.png", "large": "eth-l.png", "slug": "ethereum", "price_btc": 0.05, "score": 1}},
    {"item": {"id": "solana", "coin_id": 4128, "name": "Solana", "symbol": "SOL", "market_cap_rank": 5, "thumb": "sol.png", "small": "sol-s.png", "large": "sol-l.png", "slug": "solana", "price_btc": 0.003, "score": 2}}
  ],
  "nfts": [],
  "categories": []
}
```

Write to `/Users/laptop/dev/cryptozavr/tests/contract/fixtures/coingecko/categories.json`:
```json
[
  {"id": "layer-1", "name": "Layer 1 (L1)", "market_cap": 1500000000000, "market_cap_change_24h": 2.1, "content": "", "top_3_coins_id": ["bitcoin", "ethereum", "solana"], "top_3_coins": [], "volume_24h": 45000000000, "updated_at": "2026-04-21T10:00:00.000Z"},
  {"id": "decentralized-finance-defi", "name": "Decentralized Finance (DeFi)", "market_cap": 80000000000, "market_cap_change_24h": -0.5, "content": "", "top_3_coins_id": [], "top_3_coins": [], "volume_24h": 5000000000, "updated_at": "2026-04-21T10:00:00.000Z"},
  {"id": "meme-token", "name": "Meme", "market_cap": 60000000000, "market_cap_change_24h": 5.3, "content": "", "top_3_coins_id": [], "top_3_coins": [], "volume_24h": 8000000000, "updated_at": "2026-04-21T10:00:00.000Z"}
]
```

- [ ] **Step 2: Failing tests**

Write to `tests/unit/infrastructure/providers/adapters/test_coingecko_adapter.py`:
```python
"""Test CoinGeckoAdapter pure functions on saved fixtures."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.adapters.coingecko_adapter import (
    CoinGeckoAdapter,
)

FIXTURE_DIR = (
    Path(__file__).resolve().parents[4] / "contract" / "fixtures" / "coingecko"
)

@pytest.fixture
def registry() -> SymbolRegistry:
    return SymbolRegistry()

@pytest.fixture
def btc_symbol(registry: SymbolRegistry):
    return registry.get(
        VenueId.COINGECKO, "BTC", "USD",
        market_type=MarketType.SPOT, native_symbol="bitcoin",
    )

class TestSimplePriceToTicker:
    def test_happy_path(self, btc_symbol) -> None:
        raw = json.loads((FIXTURE_DIR / "simple_price_btc.json").read_text())
        ticker = CoinGeckoAdapter.simple_price_to_ticker(
            raw, coin_id="bitcoin", vs_currency="usd", symbol=btc_symbol,
        )
        assert ticker.last == Decimal("65000.5")
        assert ticker.volume_24h == Decimal("45230000000.0")
        assert ticker.change_24h_pct is not None
        assert ticker.change_24h_pct.value == Decimal("2.5")
        assert ticker.quality.source.venue_id == "coingecko"
        assert ticker.quality.source.endpoint == "simple_price"

    def test_missing_coin_raises(self, btc_symbol) -> None:
        with pytest.raises(KeyError):
            CoinGeckoAdapter.simple_price_to_ticker(
                {}, coin_id="bitcoin", vs_currency="usd", symbol=btc_symbol,
            )

class TestTrendingToAssets:
    def test_happy_path(self) -> None:
        raw = json.loads((FIXTURE_DIR / "trending.json").read_text())
        assets = CoinGeckoAdapter.trending_to_assets(raw)
        assert len(assets) == 3
        assert assets[0].code == "BTC"
        assert assets[0].name == "Bitcoin"
        assert assets[0].coingecko_id == "bitcoin"
        assert assets[0].market_cap_rank == 1

class TestCategoriesToList:
    def test_happy_path(self) -> None:
        raw = json.loads((FIXTURE_DIR / "categories.json").read_text())
        cats = CoinGeckoAdapter.categories_to_list(raw)
        assert len(cats) == 3
        assert cats[0]["id"] == "layer-1"
        assert cats[0]["market_cap"] == 1500000000000
        # Returns raw dict list — no Domain wrapper for categories yet.
```

- [ ] **Step 3: FAIL**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/infrastructure/providers/adapters/test_coingecko_adapter.py -v
```

- [ ] **Step 4: Implement**

Write to `/Users/laptop/dev/cryptozavr/src/cryptozavr/infrastructure/providers/adapters/coingecko_adapter.py`:
```python
"""CoinGeckoAdapter: raw JSON → Domain entities."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from cryptozavr.domain.assets import Asset
from cryptozavr.domain.market_data import Ticker
from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Instant, Percentage

class CoinGeckoAdapter:
    """Static conversions from CoinGecko REST JSON to Domain entities."""

    @staticmethod
    def simple_price_to_ticker(
        raw: Mapping[str, Any],
        *,
        coin_id: str,
        vs_currency: str,
        symbol: Symbol,
    ) -> Ticker:
        """Map /simple/price response to Domain Ticker.

        Expected shape: {"<coin_id>": {"<vs>": <price>, "<vs>_24h_vol": <vol>,
                          "<vs>_24h_change": <pct>, "last_updated_at": <ts>}}
        """
        entry = raw[coin_id]
        last = Decimal(str(entry[vs_currency]))
        volume_24h_key = f"{vs_currency}_24h_vol"
        change_24h_key = f"{vs_currency}_24h_change"
        volume_24h = (
            Decimal(str(entry[volume_24h_key]))
            if volume_24h_key in entry else None
        )
        change_pct = (
            Percentage(value=Decimal(str(entry[change_24h_key])))
            if change_24h_key in entry else None
        )
        ts = int(entry.get("last_updated_at", 0))
        observed_at = (
            Instant.from_ms(ts * 1000) if ts else Instant.now()
        )
        return Ticker(
            symbol=symbol,
            last=last,
            observed_at=observed_at,
            quality=_fresh_quality(endpoint="simple_price"),
            volume_24h=volume_24h,
            change_24h_pct=change_pct,
        )

    @staticmethod
    def trending_to_assets(raw: Mapping[str, Any]) -> list[Asset]:
        """Map /search/trending response to list of Assets."""
        coins = raw.get("coins", [])
        return [
            Asset(
                code=coin["item"]["symbol"].upper(),
                name=coin["item"].get("name"),
                coingecko_id=coin["item"].get("id"),
                market_cap_rank=coin["item"].get("market_cap_rank"),
            )
            for coin in coins
        ]

    @staticmethod
    def categories_to_list(
        raw: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        """Map /coins/categories response to plain list of dicts.

        Category Domain entity is not yet defined; callers receive the raw
        dicts (with id/name/market_cap/market_cap_change_24h/volume_24h).
        """
        return [dict(c) for c in raw]

def _fresh_quality(*, endpoint: str) -> DataQuality:
    return DataQuality(
        source=Provenance(venue_id="coingecko", endpoint=endpoint),
        fetched_at=Instant.now(),
        staleness=Staleness.FRESH,
        confidence=Confidence.HIGH,
        cache_hit=False,
    )
```

- [ ] **Step 5: PASS (5 tests).**
- [ ] **Step 6: Mypy + commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add \
  src/cryptozavr/infrastructure/providers/adapters/coingecko_adapter.py \
  tests/unit/infrastructure/providers/adapters/test_coingecko_adapter.py \
  tests/contract/fixtures/coingecko/
```

Commit:
```bash
feat(providers): add CoinGeckoAdapter + coingecko fixtures

Static conversions: simple_price -> Ticker, trending -> list[Asset],
categories -> list[dict]. Three hand-written fixtures for contract tests.
```

---

### Task 2: CoinGeckoProvider (respx-mocked httpx)

**Files:**
- Create: `src/cryptozavr/infrastructure/providers/coingecko_provider.py`
- Create: `tests/unit/infrastructure/providers/test_coingecko_provider.py`

- [ ] **Step 1: Failing tests**

Write to `tests/unit/infrastructure/providers/test_coingecko_provider.py`:
```python
"""Test CoinGeckoProvider with respx-mocked httpx."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from cryptozavr.domain.exceptions import (
    ProviderUnavailableError,
    RateLimitExceededError,
)
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.coingecko_provider import (
    CoinGeckoProvider,
)
from cryptozavr.infrastructure.providers.http import HttpClientRegistry
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

FIXTURE_DIR = (
    Path(__file__).resolve().parents[3] / "contract" / "fixtures" / "coingecko"
)
BASE_URL = "https://api.coingecko.com/api/v3"

@pytest.fixture
def registry() -> SymbolRegistry:
    return SymbolRegistry()

@pytest.fixture
def btc_symbol(registry: SymbolRegistry):
    return registry.get(
        VenueId.COINGECKO, "BTC", "USD",
        market_type=MarketType.SPOT, native_symbol="bitcoin",
    )

@pytest.fixture
async def http_registry():
    reg = HttpClientRegistry()
    yield reg
    await reg.close_all()

async def _build_provider(http_registry: HttpClientRegistry) -> CoinGeckoProvider:
    client = await http_registry.get("coingecko", base_url=BASE_URL)
    return CoinGeckoProvider(
        state=VenueState(VenueId.COINGECKO),
        client=client,
    )

@pytest.mark.asyncio
@respx.mock
async def test_fetch_ticker_happy_path(http_registry, btc_symbol) -> None:
    raw = json.loads((FIXTURE_DIR / "simple_price_btc.json").read_text())
    respx.get(f"{BASE_URL}/simple/price").mock(
        return_value=httpx.Response(200, json=raw),
    )
    provider = await _build_provider(http_registry)

    ticker = await provider.fetch_ticker(btc_symbol)

    assert ticker.last == Decimal("65000.5")
    assert ticker.quality.source.venue_id == "coingecko"

@pytest.mark.asyncio
@respx.mock
async def test_list_trending_returns_assets(http_registry) -> None:
    raw = json.loads((FIXTURE_DIR / "trending.json").read_text())
    respx.get(f"{BASE_URL}/search/trending").mock(
        return_value=httpx.Response(200, json=raw),
    )
    provider = await _build_provider(http_registry)

    assets = await provider.list_trending(limit=15)

    assert len(assets) == 3
    assert assets[0].code == "BTC"

@pytest.mark.asyncio
@respx.mock
async def test_list_categories_returns_list(http_registry) -> None:
    raw = json.loads((FIXTURE_DIR / "categories.json").read_text())
    respx.get(f"{BASE_URL}/coins/categories").mock(
        return_value=httpx.Response(200, json=raw),
    )
    provider = await _build_provider(http_registry)

    cats = await provider.list_categories(limit=30)

    assert len(cats) == 3
    assert cats[0]["id"] == "layer-1"

@pytest.mark.asyncio
@respx.mock
async def test_rate_limit_translated(http_registry, btc_symbol) -> None:
    respx.get(f"{BASE_URL}/simple/price").mock(
        return_value=httpx.Response(429, json={"error": "rate limit"}),
    )
    provider = await _build_provider(http_registry)

    with pytest.raises(RateLimitExceededError):
        await provider.fetch_ticker(btc_symbol)

@pytest.mark.asyncio
@respx.mock
async def test_network_error_translated(http_registry, btc_symbol) -> None:
    respx.get(f"{BASE_URL}/simple/price").mock(
        side_effect=httpx.ConnectError("connection refused"),
    )
    provider = await _build_provider(http_registry)

    with pytest.raises(ProviderUnavailableError):
        await provider.fetch_ticker(btc_symbol)

@pytest.mark.asyncio
async def test_load_markets_is_noop(http_registry) -> None:
    provider = await _build_provider(http_registry)
    await provider.load_markets()  # no raise, no HTTP call
```

- [ ] **Step 2: FAIL**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/infrastructure/providers/test_coingecko_provider.py -v
```

- [ ] **Step 3: Implement**

Write to `/Users/laptop/dev/cryptozavr/src/cryptozavr/infrastructure/providers/coingecko_provider.py`:
```python
"""CoinGeckoProvider: BaseProvider subclass using httpx + HttpClientRegistry."""

from __future__ import annotations

from typing import Any

import httpx

from cryptozavr.domain.assets import Asset
from cryptozavr.domain.exceptions import (
    ProviderUnavailableError,
    RateLimitExceededError,
)
from cryptozavr.domain.market_data import Ticker
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.venues import VenueId
from cryptozavr.infrastructure.providers.adapters.coingecko_adapter import (
    CoinGeckoAdapter,
)
from cryptozavr.infrastructure.providers.base import BaseProvider
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

class CoinGeckoProvider(BaseProvider):
    """CoinGecko REST provider.

    Aggregator, not an exchange — only ticker/trending/categories supported.
    OHLCV/orderbook/trades inherit NotImplementedError defaults from BaseProvider.
    """

    def __init__(
        self,
        *,
        state: VenueState,
        client: httpx.AsyncClient,
    ) -> None:
        super().__init__(venue_id=VenueId.COINGECKO, state=state)
        self._client = client

    # ---- BaseProvider hooks ----

    async def _ensure_markets_loaded(self) -> None:
        """No-op. CoinGecko has no 'markets' in CEX sense."""
        return None

    async def _fetch_ticker_raw(self, symbol: Symbol) -> Any:
        coin_id = symbol.native_symbol
        vs = symbol.quote.lower()
        response = await self._client.get(
            "/simple/price",
            params={
                "ids": coin_id,
                "vs_currencies": vs,
                "include_24hr_vol": "true",
                "include_24hr_change": "true",
                "include_last_updated_at": "true",
            },
        )
        self._raise_for_status(response)
        return response.json()

    def _normalize_ticker(self, raw: Any, symbol: Symbol) -> Ticker:
        return CoinGeckoAdapter.simple_price_to_ticker(
            raw,
            coin_id=symbol.native_symbol,
            vs_currency=symbol.quote.lower(),
            symbol=symbol,
        )

    def _translate_exception(self, exc: Exception) -> Exception:
        if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
            return ProviderUnavailableError(str(exc))
        return exc

    # ---- CoinGecko-specific endpoints (outside BaseProvider pipeline) ----

    async def list_trending(self, *, limit: int = 15) -> list[Asset]:
        """/search/trending → list[Asset] (trimmed to limit)."""
        self._state.require_operational()
        try:
            response = await self._client.get("/search/trending")
            self._raise_for_status(response)
        except Exception as exc:
            raise self._translate_exception(exc) from exc
        assets = CoinGeckoAdapter.trending_to_assets(response.json())
        return assets[:limit]

    async def list_categories(self, *, limit: int = 30) -> list[dict[str, Any]]:
        """/coins/categories → list of category dicts (trimmed to limit)."""
        self._state.require_operational()
        try:
            response = await self._client.get("/coins/categories")
            self._raise_for_status(response)
        except Exception as exc:
            raise self._translate_exception(exc) from exc
        return CoinGeckoAdapter.categories_to_list(response.json())[:limit]

    async def close(self) -> None:
        """Client is owned by HttpClientRegistry — don't close here."""
        return None

    # ---- helpers ----

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code == 429:
            raise RateLimitExceededError(
                f"coingecko rate limited: {response.text[:200]}"
            )
        if response.status_code >= 500:
            raise ProviderUnavailableError(
                f"coingecko {response.status_code}: {response.text[:200]}"
            )
        response.raise_for_status()
```

- [ ] **Step 4: PASS (6 tests).**
- [ ] **Step 5: Mypy + commit**

Commit:
```text
feat(providers): add CoinGeckoProvider (httpx + HttpClientRegistry)

Aggregator provider: fetch_ticker via /simple/price, list_trending,
list_categories. OHLCV/orderbook/trades remain NotImplementedError via
BaseProvider defaults. 429 -> RateLimitExceededError; ConnectError/Timeout
-> ProviderUnavailableError. Client lifetime owned by HttpClientRegistry.
```

---

### Task 3: CoinGecko contract test

**Files:**
- Create: `tests/contract/test_coingecko_provider_contract.py`

- [ ] **Step 1: Write test**

Write to `tests/contract/test_coingecko_provider_contract.py`:
```python
"""Contract tests: CoinGeckoProvider against saved fixtures via respx."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.coingecko_provider import (
    CoinGeckoProvider,
)
from cryptozavr.infrastructure.providers.http import HttpClientRegistry
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

pytestmark = pytest.mark.contract

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "coingecko"
BASE_URL = "https://api.coingecko.com/api/v3"

@pytest.fixture
def registry() -> SymbolRegistry:
    return SymbolRegistry()

@pytest.fixture
def btc_symbol(registry: SymbolRegistry):
    return registry.get(
        VenueId.COINGECKO, "BTC", "USD",
        market_type=MarketType.SPOT, native_symbol="bitcoin",
    )

@respx.mock
async def test_full_ticker_path(btc_symbol) -> None:
    raw = json.loads((FIXTURE_DIR / "simple_price_btc.json").read_text())
    respx.get(f"{BASE_URL}/simple/price").mock(
        return_value=httpx.Response(200, json=raw),
    )
    reg = HttpClientRegistry()
    try:
        client = await reg.get("coingecko", base_url=BASE_URL)
        provider = CoinGeckoProvider(
            state=VenueState(VenueId.COINGECKO),
            client=client,
        )
        ticker = await provider.fetch_ticker(btc_symbol)
        assert ticker.last == Decimal("65000.5")
    finally:
        await reg.close_all()

@respx.mock
async def test_full_trending_path() -> None:
    raw = json.loads((FIXTURE_DIR / "trending.json").read_text())
    respx.get(f"{BASE_URL}/search/trending").mock(
        return_value=httpx.Response(200, json=raw),
    )
    reg = HttpClientRegistry()
    try:
        client = await reg.get("coingecko", base_url=BASE_URL)
        provider = CoinGeckoProvider(
            state=VenueState(VenueId.COINGECKO),
            client=client,
        )
        assets = await provider.list_trending(limit=2)
        assert len(assets) == 2
        assert assets[0].code == "BTC"
    finally:
        await reg.close_all()
```

- [ ] **Step 2: Run (contract mark)**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/contract/test_coingecko_provider_contract.py -v -m contract
```

Expected: 2 passed.

- [ ] **Step 3: Commit**

Commit:
```text
test(providers): add CoinGecko contract tests via respx + fixtures

Two end-to-end paths (ticker, trending) exercise CoinGeckoProvider +
CoinGeckoAdapter + HttpClientRegistry stack without network.
```

---

### Task 4: VenueState full State pattern

**Files:**
- Modify: `src/cryptozavr/infrastructure/providers/state/venue_state.py`
- Create: `src/cryptozavr/infrastructure/providers/state/handlers.py`
- Modify: `tests/unit/infrastructure/providers/state/test_venue_state.py` (add transition tests)
- Create: `tests/unit/infrastructure/providers/state/test_handlers.py`

- [ ] **Step 1: Write failing transition tests**

Append to `tests/unit/infrastructure/providers/state/test_venue_state.py`:
```python
from cryptozavr.domain.exceptions import RateLimitExceededError
from freezegun import freeze_time

class TestTransitions:
    def test_healthy_degrades_after_3_errors(self) -> None:
        state = VenueState(venue_id=VenueId.KUCOIN)
        for _ in range(3):
            state.on_request_failed(Exception("boom"))
        assert state.kind == VenueStateKind.DEGRADED

    def test_degraded_recovers_after_5_successes(self) -> None:
        state = VenueState(
            venue_id=VenueId.KUCOIN, kind=VenueStateKind.DEGRADED,
        )
        for _ in range(5):
            state.on_request_succeeded()
        assert state.kind == VenueStateKind.HEALTHY

    def test_rate_limit_error_transitions_to_rate_limited(self) -> None:
        state = VenueState(venue_id=VenueId.KUCOIN)
        state.on_request_failed(RateLimitExceededError("429"))
        assert state.kind == VenueStateKind.RATE_LIMITED

    def test_rate_limited_expires_back_to_healthy_after_cooldown(self) -> None:
        with freeze_time("2026-04-21 10:00:00") as frozen:
            state = VenueState(venue_id=VenueId.KUCOIN)
            state.on_request_failed(RateLimitExceededError("429"))
            assert state.kind == VenueStateKind.RATE_LIMITED
            # require_operational should raise now
            with pytest.raises(ProviderUnavailableError):
                state.require_operational()
            # After cooldown (30s default) + one success tick:
            frozen.tick(31)
            state.on_request_started()  # cooldown check happens here
            assert state.kind == VenueStateKind.HEALTHY

    def test_mark_down_forces_down_state(self) -> None:
        state = VenueState(venue_id=VenueId.KUCOIN)
        state.mark_down()
        assert state.kind == VenueStateKind.DOWN
        with pytest.raises(ProviderUnavailableError):
            state.require_operational()

    def test_success_resets_error_count(self) -> None:
        state = VenueState(venue_id=VenueId.KUCOIN)
        state.on_request_failed(Exception("boom"))
        state.on_request_failed(Exception("boom"))
        state.on_request_succeeded()
        # Now need 3 more errors to degrade
        state.on_request_failed(Exception("boom"))
        state.on_request_failed(Exception("boom"))
        assert state.kind == VenueStateKind.HEALTHY
        state.on_request_failed(Exception("boom"))
        assert state.kind == VenueStateKind.DEGRADED
```

Write to `tests/unit/infrastructure/providers/state/test_handlers.py`:
```python
"""Per-handler tests: each handler reports the right VenueStateKind."""

from __future__ import annotations

from cryptozavr.domain.venues import VenueStateKind
from cryptozavr.infrastructure.providers.state.handlers import (
    DegradedStateHandler,
    DownStateHandler,
    HealthyStateHandler,
    RateLimitedStateHandler,
)

def test_healthy_kind() -> None:
    assert HealthyStateHandler().kind == VenueStateKind.HEALTHY

def test_degraded_kind() -> None:
    assert DegradedStateHandler().kind == VenueStateKind.DEGRADED

def test_rate_limited_kind() -> None:
    assert RateLimitedStateHandler(cooldown_sec=30).kind == VenueStateKind.RATE_LIMITED

def test_down_kind() -> None:
    assert DownStateHandler().kind == VenueStateKind.DOWN
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement handlers**

Write to `/Users/laptop/dev/cryptozavr/src/cryptozavr/infrastructure/providers/state/handlers.py`:
```python
"""State pattern handlers: one class per VenueStateKind.

VenueState (context) holds the current handler and delegates on_* events.
Handlers return a new handler instance when transition is warranted.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from cryptozavr.domain.exceptions import (
    ProviderUnavailableError,
    RateLimitExceededError,
)
from cryptozavr.domain.venues import VenueStateKind

@dataclass
class _TransitionContext:
    error_count: int
    success_streak: int

class StateHandler:
    """Base: default no-op behaviour."""

    kind: VenueStateKind = VenueStateKind.HEALTHY

    def on_request_started(
        self, ctx: _TransitionContext,
    ) -> StateHandler | None:
        return None

    def on_request_succeeded(
        self, ctx: _TransitionContext,
    ) -> StateHandler | None:
        return None

    def on_request_failed(
        self, exc: Exception, ctx: _TransitionContext,
    ) -> StateHandler | None:
        return None

    def check_operational(self) -> None:
        return None

class HealthyStateHandler(StateHandler):
    kind = VenueStateKind.HEALTHY

    def on_request_failed(
        self, exc: Exception, ctx: _TransitionContext,
    ) -> StateHandler | None:
        if isinstance(exc, RateLimitExceededError):
            return RateLimitedStateHandler(cooldown_sec=30)
        if ctx.error_count >= 3:
            return DegradedStateHandler()
        return None

class DegradedStateHandler(StateHandler):
    kind = VenueStateKind.DEGRADED

    def on_request_succeeded(
        self, ctx: _TransitionContext,
    ) -> StateHandler | None:
        if ctx.success_streak >= 5:
            return HealthyStateHandler()
        return None

    def on_request_failed(
        self, exc: Exception, ctx: _TransitionContext,
    ) -> StateHandler | None:
        if isinstance(exc, RateLimitExceededError):
            return RateLimitedStateHandler(cooldown_sec=30)
        return None

class RateLimitedStateHandler(StateHandler):
    kind = VenueStateKind.RATE_LIMITED

    def __init__(self, *, cooldown_sec: int) -> None:
        self._cooldown_until = time.monotonic() + cooldown_sec

    def on_request_started(
        self, ctx: _TransitionContext,
    ) -> StateHandler | None:
        if time.monotonic() >= self._cooldown_until:
            return HealthyStateHandler()
        return None

    def check_operational(self) -> None:
        if time.monotonic() < self._cooldown_until:
            raise ProviderUnavailableError("venue is rate_limited")

class DownStateHandler(StateHandler):
    kind = VenueStateKind.DOWN

    def check_operational(self) -> None:
        raise ProviderUnavailableError("venue is down")
```

- [ ] **Step 4: Replace VenueState body**

Replace the content of `/Users/laptop/dev/cryptozavr/src/cryptozavr/infrastructure/providers/state/venue_state.py` with:
```python
"""VenueState: State pattern context delegating to handlers."""

from __future__ import annotations

from cryptozavr.domain.exceptions import RateLimitExceededError
from cryptozavr.domain.venues import VenueId, VenueStateKind
from cryptozavr.infrastructure.providers.state.handlers import (
    DegradedStateHandler,
    DownStateHandler,
    HealthyStateHandler,
    RateLimitedStateHandler,
    StateHandler,
    _TransitionContext,
)

_INITIAL_HANDLERS: dict[VenueStateKind, type[StateHandler]] = {
    VenueStateKind.HEALTHY: HealthyStateHandler,
    VenueStateKind.DEGRADED: DegradedStateHandler,
    VenueStateKind.DOWN: DownStateHandler,
}

class VenueState:
    """Context: holds current handler + transition state (error/success counters)."""

    def __init__(
        self,
        venue_id: VenueId,
        *,
        kind: VenueStateKind = VenueStateKind.HEALTHY,
    ) -> None:
        self.venue_id = venue_id
        cls = _INITIAL_HANDLERS.get(kind)
        if cls is None:
            # RateLimitedStateHandler takes cooldown arg; not used for manual init.
            raise ValueError(
                f"cannot initialize VenueState with kind={kind}; "
                "use default or one of HEALTHY/DEGRADED/DOWN"
            )
        self._handler: StateHandler = cls()
        self._ctx = _TransitionContext(error_count=0, success_streak=0)

    @property
    def kind(self) -> VenueStateKind:
        return self._handler.kind

    def require_operational(self) -> None:
        self._handler.check_operational()

    def transition_to(self, new_kind: VenueStateKind) -> None:
        """Backward-compat helper (M2.3a API). Prefer on_request_*."""
        cls = _INITIAL_HANDLERS.get(new_kind)
        if cls is None:
            raise ValueError(f"transition_to cannot create {new_kind} directly")
        self._handler = cls()
        self._reset_counters()

    def mark_down(self) -> None:
        self._handler = DownStateHandler()
        self._reset_counters()

    def on_request_started(self) -> None:
        new = self._handler.on_request_started(self._ctx)
        if new is not None:
            self._handler = new
            self._reset_counters()

    def on_request_succeeded(self) -> None:
        self._ctx.success_streak += 1
        self._ctx.error_count = 0
        new = self._handler.on_request_succeeded(self._ctx)
        if new is not None:
            self._handler = new
            self._reset_counters()

    def on_request_failed(self, exc: Exception) -> None:
        self._ctx.error_count += 1
        self._ctx.success_streak = 0
        new = self._handler.on_request_failed(exc, self._ctx)
        if new is not None:
            self._handler = new
            self._reset_counters()

    def _reset_counters(self) -> None:
        self._ctx.error_count = 0
        self._ctx.success_streak = 0
```

Note: the `RateLimitedStateHandler(cooldown_sec=30)` is returned from HealthyStateHandler/DegradedStateHandler — not directly instantiated via `_INITIAL_HANDLERS`. This is intentional: RATE_LIMITED is always an automatic transition.

Test `test_can_initialize_with_kind` in test_venue_state.py that set kind=RATE_LIMITED directly will now fail — that test needs to change. Update it in place:

Find in test_venue_state.py:
```python
    def test_can_initialize_with_kind(self) -> None:
        state = VenueState(venue_id=VenueId.KUCOIN, kind=VenueStateKind.DEGRADED)
        assert state.kind == VenueStateKind.DEGRADED
```

This still works. Find:
```python
    def test_require_operational_rate_limited_raises(self) -> None:
        state = VenueState(
            venue_id=VenueId.KUCOIN, kind=VenueStateKind.RATE_LIMITED,
        )
        with pytest.raises(ProviderUnavailableError, match="rate_limited"):
            state.require_operational()
```

Replace with:
```python
    def test_require_operational_rate_limited_raises(self) -> None:
        state = VenueState(venue_id=VenueId.KUCOIN)
        state.on_request_failed(RateLimitExceededError("429"))
        assert state.kind == VenueStateKind.RATE_LIMITED
        with pytest.raises(ProviderUnavailableError, match="rate_limited"):
            state.require_operational()
```

Also remove the `transition_to` test that assumed RATE_LIMITED transitions — or adjust to only use HEALTHY/DEGRADED/DOWN in transition_to.

- [ ] **Step 5: PASS**

All tests (original 7 + 6 new transitions + 4 handler) = 17 pass.

- [ ] **Step 6: Commit**

Commit:
```text
feat(providers): upgrade VenueState to full State pattern

4 handlers (Healthy/Degraded/RateLimited/Down) with automatic
transitions. Healthy→Degraded after 3 consecutive errors; Degraded→
Healthy after 5 successes; RateLimitExceededError→RateLimited 30s
cooldown; RateLimited expiry on next request→Healthy. mark_down()
forces Down.
```

---

### Task 5: RetryDecorator

**Files:**
- Create: `src/cryptozavr/infrastructure/providers/decorators/__init__.py`
- Create: `src/cryptozavr/infrastructure/providers/decorators/retry.py`
- Create: `tests/unit/infrastructure/providers/decorators/__init__.py`
- Create: `tests/unit/infrastructure/providers/decorators/test_retry_decorator.py`

- [ ] **Step 1: Failing tests**

Write empty `tests/unit/infrastructure/providers/decorators/__init__.py`.

Write to `tests/unit/infrastructure/providers/decorators/test_retry_decorator.py`:
```python
"""Test RetryDecorator: exponential backoff on ProviderUnavailableError."""

from __future__ import annotations

import pytest

from cryptozavr.domain.exceptions import (
    ProviderUnavailableError,
    RateLimitExceededError,
)
from cryptozavr.infrastructure.providers.decorators.retry import RetryDecorator

class _StubProvider:
    venue_id = "test"

    def __init__(
        self,
        *,
        failures: int = 0,
        rate_limit_after: int = -1,
    ) -> None:
        self._failures = failures
        self._rate_limit_after = rate_limit_after
        self.calls = 0

    async def fetch_ticker(self, symbol: str) -> str:
        self.calls += 1
        if self.calls <= self._rate_limit_after:
            raise RateLimitExceededError("429")
        if self.calls <= self._failures:
            raise ProviderUnavailableError("timeout")
        return f"ticker-{symbol}"

@pytest.mark.asyncio
async def test_succeeds_on_first_attempt() -> None:
    provider = _StubProvider(failures=0)
    decorator = RetryDecorator(
        provider, max_attempts=3, base_delay=0.001, jitter=0.0,
    )
    result = await decorator.fetch_ticker("BTC/USDT")
    assert result == "ticker-BTC/USDT"
    assert provider.calls == 1

@pytest.mark.asyncio
async def test_retries_on_provider_unavailable() -> None:
    provider = _StubProvider(failures=2)
    decorator = RetryDecorator(
        provider, max_attempts=3, base_delay=0.001, jitter=0.0,
    )
    result = await decorator.fetch_ticker("BTC/USDT")
    assert result == "ticker-BTC/USDT"
    assert provider.calls == 3

@pytest.mark.asyncio
async def test_raises_after_max_attempts() -> None:
    provider = _StubProvider(failures=5)
    decorator = RetryDecorator(
        provider, max_attempts=3, base_delay=0.001, jitter=0.0,
    )
    with pytest.raises(ProviderUnavailableError):
        await decorator.fetch_ticker("BTC/USDT")
    assert provider.calls == 3

@pytest.mark.asyncio
async def test_does_not_retry_on_rate_limit() -> None:
    provider = _StubProvider(rate_limit_after=5)
    decorator = RetryDecorator(
        provider, max_attempts=3, base_delay=0.001, jitter=0.0,
    )
    with pytest.raises(RateLimitExceededError):
        await decorator.fetch_ticker("BTC/USDT")
    assert provider.calls == 1
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

Write to `/Users/laptop/dev/cryptozavr/src/cryptozavr/infrastructure/providers/decorators/__init__.py`:
```python
"""Provider decorators: Retry, RateLimit, Caching, Logging."""
```

Write to `/Users/laptop/dev/cryptozavr/src/cryptozavr/infrastructure/providers/decorators/retry.py`:
```python
"""RetryDecorator: exponential backoff + jitter for ProviderUnavailableError.

Excludes RateLimitExceededError (that's what RateLimitDecorator is for).
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

from cryptozavr.domain.exceptions import ProviderUnavailableError
from cryptozavr.domain.interfaces import MarketDataProvider

class RetryDecorator:
    """Wraps a MarketDataProvider, retrying transient failures."""

    def __init__(
        self,
        inner: MarketDataProvider,
        *,
        max_attempts: int = 3,
        base_delay: float = 0.5,
        jitter: float = 0.2,
    ) -> None:
        self._inner = inner
        self._max_attempts = max_attempts
        self._base_delay = base_delay
        self._jitter = jitter
        self.venue_id = inner.venue_id

    def __getattr__(self, name: str) -> Any:
        """Forward missing attributes (e.g. non-async helpers) to inner."""
        return getattr(self._inner, name)

    async def load_markets(self) -> None:
        await self._retry(self._inner.load_markets)

    async def fetch_ticker(self, symbol: Any) -> Any:
        return await self._retry(self._inner.fetch_ticker, symbol)

    async def fetch_ohlcv(self, *args: Any, **kwargs: Any) -> Any:
        return await self._retry(self._inner.fetch_ohlcv, *args, **kwargs)

    async def fetch_order_book(self, *args: Any, **kwargs: Any) -> Any:
        return await self._retry(self._inner.fetch_order_book, *args, **kwargs)

    async def fetch_trades(self, *args: Any, **kwargs: Any) -> Any:
        return await self._retry(self._inner.fetch_trades, *args, **kwargs)

    async def close(self) -> None:
        await self._inner.close()

    async def _retry(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        last_exc: Exception | None = None
        for attempt in range(self._max_attempts):
            try:
                return await fn(*args, **kwargs)
            except ProviderUnavailableError as exc:
                last_exc = exc
                if attempt == self._max_attempts - 1:
                    raise
                delay = self._base_delay * (2 ** attempt) + random.uniform(
                    0, self._jitter
                )
                await asyncio.sleep(delay)
        assert last_exc is not None
        raise last_exc
```

- [ ] **Step 4: PASS (4 tests).**
- [ ] **Step 5: Mypy + commit**

Commit:
```text
feat(providers): add RetryDecorator (exponential backoff)

Retries ProviderUnavailableError up to max_attempts with exponential
delay (base_delay * 2^attempt) + random jitter. Intentionally skips
RateLimitExceededError — that's RateLimitDecorator's territory.
```

---

### Task 6: RateLimitDecorator

**Files:**
- Create: `src/cryptozavr/infrastructure/providers/decorators/rate_limit.py`
- Create: `tests/unit/infrastructure/providers/decorators/test_rate_limit_decorator.py`

- [ ] **Step 1: Failing tests**

Write to `tests/unit/infrastructure/providers/decorators/test_rate_limit_decorator.py`:
```python
"""Test RateLimitDecorator: acquires token from RateLimiterRegistry."""

from __future__ import annotations

import time

import pytest

from cryptozavr.infrastructure.providers.decorators.rate_limit import (
    RateLimitDecorator,
)
from cryptozavr.infrastructure.providers.rate_limiters import (
    RateLimiterRegistry,
)

class _StubProvider:
    venue_id = "kucoin"

    def __init__(self) -> None:
        self.calls = 0

    async def fetch_ticker(self, symbol: str) -> str:
        self.calls += 1
        return f"ticker-{symbol}"

@pytest.fixture
def registry() -> RateLimiterRegistry:
    reg = RateLimiterRegistry()
    reg.register("kucoin", rate_per_sec=100.0, capacity=1)
    return reg

@pytest.mark.asyncio
async def test_acquires_token_before_call(
    registry: RateLimiterRegistry,
) -> None:
    provider = _StubProvider()
    decorator = RateLimitDecorator(provider, limiter=registry.get("kucoin"))
    result = await decorator.fetch_ticker("BTC/USDT")
    assert result == "ticker-BTC/USDT"
    assert provider.calls == 1

@pytest.mark.asyncio
async def test_blocks_when_rate_exceeded(
    registry: RateLimiterRegistry,
) -> None:
    provider = _StubProvider()
    decorator = RateLimitDecorator(provider, limiter=registry.get("kucoin"))
    # capacity=1, rate=100/s -> second call blocks ~10ms.
    await decorator.fetch_ticker("BTC/USDT")
    start = time.monotonic()
    await decorator.fetch_ticker("BTC/USDT")
    elapsed = time.monotonic() - start
    assert elapsed >= 0.005  # at least ~10ms wait, some slack
    assert provider.calls == 2

@pytest.mark.asyncio
async def test_provider_exception_does_not_consume_extra_tokens(
    registry: RateLimiterRegistry,
) -> None:
    class _FailingProvider:
        venue_id = "kucoin"
        calls = 0

        async def fetch_ticker(self, symbol: str) -> str:
            self.calls += 1
            raise ValueError("boom")

    provider = _FailingProvider()
    decorator = RateLimitDecorator(provider, limiter=registry.get("kucoin"))
    with pytest.raises(ValueError):
        await decorator.fetch_ticker("BTC/USDT")
    assert provider.calls == 1
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

Write to `/Users/laptop/dev/cryptozavr/src/cryptozavr/infrastructure/providers/decorators/rate_limit.py`:
```python
"""RateLimitDecorator: acquires a token before each provider call."""

from __future__ import annotations

from typing import Any

from cryptozavr.domain.interfaces import MarketDataProvider
from cryptozavr.infrastructure.providers.rate_limiters import TokenBucket

class RateLimitDecorator:
    """Wraps a MarketDataProvider, throttling calls via a TokenBucket."""

    def __init__(
        self,
        inner: MarketDataProvider,
        *,
        limiter: TokenBucket,
    ) -> None:
        self._inner = inner
        self._limiter = limiter
        self.venue_id = inner.venue_id

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def load_markets(self) -> None:
        await self._limiter.acquire()
        await self._inner.load_markets()

    async def fetch_ticker(self, symbol: Any) -> Any:
        await self._limiter.acquire()
        return await self._inner.fetch_ticker(symbol)

    async def fetch_ohlcv(self, *args: Any, **kwargs: Any) -> Any:
        await self._limiter.acquire()
        return await self._inner.fetch_ohlcv(*args, **kwargs)

    async def fetch_order_book(self, *args: Any, **kwargs: Any) -> Any:
        await self._limiter.acquire()
        return await self._inner.fetch_order_book(*args, **kwargs)

    async def fetch_trades(self, *args: Any, **kwargs: Any) -> Any:
        await self._limiter.acquire()
        return await self._inner.fetch_trades(*args, **kwargs)

    async def close(self) -> None:
        await self._inner.close()
```

- [ ] **Step 4: PASS (3 tests).**
- [ ] **Step 5: Mypy + commit**

Commit:
```bash
feat(providers): add RateLimitDecorator

Acquires one token from TokenBucket before each provider call.
Token is consumed before invocation — if the inner call fails, the
token is gone, preventing retry spam under duress. Paired with
RateLimiterRegistry configured at DI wiring time.
```

---

### Task 7: InMemoryCachingDecorator + Clock

**Files:**
- Create: `src/cryptozavr/infrastructure/providers/decorators/caching.py`
- Create: `tests/unit/infrastructure/providers/decorators/test_caching_decorator.py`

- [ ] **Step 1: Failing tests**

Write to `tests/unit/infrastructure/providers/decorators/test_caching_decorator.py`:
```python
"""Test InMemoryCachingDecorator: TTL cache, freezegun-controlled."""

from __future__ import annotations

import pytest
from freezegun import freeze_time

from cryptozavr.infrastructure.providers.decorators.caching import (
    InMemoryCachingDecorator,
)

class _StubProvider:
    venue_id = "kucoin"

    def __init__(self) -> None:
        self.ticker_calls = 0

    async def fetch_ticker(self, symbol: str) -> str:
        self.ticker_calls += 1
        return f"ticker-{symbol}-v{self.ticker_calls}"

@pytest.mark.asyncio
async def test_first_call_is_cache_miss() -> None:
    provider = _StubProvider()
    decorator = InMemoryCachingDecorator(provider, ticker_ttl=10.0)
    result = await decorator.fetch_ticker("BTC/USDT")
    assert result == "ticker-BTC/USDT-v1"
    assert provider.ticker_calls == 1

@pytest.mark.asyncio
async def test_second_call_within_ttl_returns_cache() -> None:
    provider = _StubProvider()
    decorator = InMemoryCachingDecorator(provider, ticker_ttl=10.0)
    with freeze_time("2026-04-21 10:00:00") as frozen:
        r1 = await decorator.fetch_ticker("BTC/USDT")
        frozen.tick(5)
        r2 = await decorator.fetch_ticker("BTC/USDT")
    assert r1 == r2
    assert provider.ticker_calls == 1  # inner called once

@pytest.mark.asyncio
async def test_call_after_ttl_refetches() -> None:
    provider = _StubProvider()
    decorator = InMemoryCachingDecorator(provider, ticker_ttl=10.0)
    with freeze_time("2026-04-21 10:00:00") as frozen:
        await decorator.fetch_ticker("BTC/USDT")
        frozen.tick(11)  # beyond TTL
        r2 = await decorator.fetch_ticker("BTC/USDT")
    assert r2 == "ticker-BTC/USDT-v2"
    assert provider.ticker_calls == 2

@pytest.mark.asyncio
async def test_different_symbols_are_independent() -> None:
    provider = _StubProvider()
    decorator = InMemoryCachingDecorator(provider, ticker_ttl=10.0)
    await decorator.fetch_ticker("BTC/USDT")
    await decorator.fetch_ticker("ETH/USDT")
    assert provider.ticker_calls == 2
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

Write to `/Users/laptop/dev/cryptozavr/src/cryptozavr/infrastructure/providers/decorators/caching.py`:
```python
"""InMemoryCachingDecorator: L0 TTL cache for ticker/ohlcv/orderbook."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from cryptozavr.domain.interfaces import MarketDataProvider

@dataclass
class _Entry:
    value: Any
    expires_at: float

class InMemoryCachingDecorator:
    """Wraps a MarketDataProvider with TTL-based in-memory caching.

    Cache key: (method_name, args_repr). TTL per method family
    (ticker, ohlcv, order_book). No cache for trades or load_markets.
    """

    def __init__(
        self,
        inner: MarketDataProvider,
        *,
        ticker_ttl: float = 5.0,
        ohlcv_ttl: float = 60.0,
        order_book_ttl: float = 3.0,
    ) -> None:
        self._inner = inner
        self._ticker_ttl = ticker_ttl
        self._ohlcv_ttl = ohlcv_ttl
        self._order_book_ttl = order_book_ttl
        self._cache: dict[str, _Entry] = {}
        self.venue_id = inner.venue_id

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def load_markets(self) -> None:
        await self._inner.load_markets()

    async def fetch_ticker(self, symbol: Any) -> Any:
        key = f"ticker:{symbol!r}"
        return await self._cached(
            key, self._ticker_ttl, self._inner.fetch_ticker, symbol,
        )

    async def fetch_ohlcv(self, *args: Any, **kwargs: Any) -> Any:
        key = f"ohlcv:{args!r}:{sorted(kwargs.items())!r}"
        return await self._cached(
            key, self._ohlcv_ttl, self._inner.fetch_ohlcv, *args, **kwargs,
        )

    async def fetch_order_book(self, *args: Any, **kwargs: Any) -> Any:
        key = f"orderbook:{args!r}:{sorted(kwargs.items())!r}"
        return await self._cached(
            key, self._order_book_ttl, self._inner.fetch_order_book,
            *args, **kwargs,
        )

    async def fetch_trades(self, *args: Any, **kwargs: Any) -> Any:
        return await self._inner.fetch_trades(*args, **kwargs)

    async def close(self) -> None:
        await self._inner.close()

    async def _cached(
        self, key: str, ttl: float, fn: Any, *args: Any, **kwargs: Any,
    ) -> Any:
        now = time.time()
        entry = self._cache.get(key)
        if entry is not None and entry.expires_at > now:
            return entry.value
        value = await fn(*args, **kwargs)
        self._cache[key] = _Entry(value=value, expires_at=now + ttl)
        return value
```

- [ ] **Step 4: PASS (4 tests).**
- [ ] **Step 5: Mypy + commit**

Commit:
```bash
feat(providers): add InMemoryCachingDecorator (TTL cache)

L0 cache for ticker/ohlcv/orderbook with per-method TTLs. Uses
time.time() so freezegun-based tests control expiration. Trades
and load_markets bypass cache. Keys are method_name + repr(args).
```

---

### Task 8: LoggingDecorator

**Files:**
- Create: `src/cryptozavr/infrastructure/providers/decorators/logging.py`
- Create: `tests/unit/infrastructure/providers/decorators/test_logging_decorator.py`

- [ ] **Step 1: Failing tests**

Write to `tests/unit/infrastructure/providers/decorators/test_logging_decorator.py`:
```python
"""Test LoggingDecorator: structlog records inner calls."""

from __future__ import annotations

import logging

import pytest

from cryptozavr.infrastructure.providers.decorators.logging import (
    LoggingDecorator,
)

class _StubProvider:
    venue_id = "kucoin"

    async def fetch_ticker(self, symbol: str) -> str:
        return f"ticker-{symbol}"

    async def fetch_ohlcv(self, symbol: str) -> str:
        raise RuntimeError("boom")

@pytest.mark.asyncio
async def test_logs_successful_call(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    provider = _StubProvider()
    decorator = LoggingDecorator(provider)
    result = await decorator.fetch_ticker("BTC/USDT")
    assert result == "ticker-BTC/USDT"
    msgs = [r.message for r in caplog.records]
    assert any("fetch_ticker" in m for m in msgs)

@pytest.mark.asyncio
async def test_logs_failed_call_and_reraises(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    provider = _StubProvider()
    decorator = LoggingDecorator(provider)
    with pytest.raises(RuntimeError, match="boom"):
        await decorator.fetch_ohlcv("BTC/USDT")
    msgs = [r.message for r in caplog.records]
    assert any("fetch_ohlcv" in m and "failed" in m.lower() for m in msgs)

@pytest.mark.asyncio
async def test_venue_id_forwarded() -> None:
    provider = _StubProvider()
    decorator = LoggingDecorator(provider)
    assert decorator.venue_id == "kucoin"
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

Write to `/Users/laptop/dev/cryptozavr/src/cryptozavr/infrastructure/providers/decorators/logging.py`:
```python
"""LoggingDecorator: structured per-call logs via stdlib logging."""

from __future__ import annotations

import logging
import time
from typing import Any

from cryptozavr.domain.interfaces import MarketDataProvider

class LoggingDecorator:
    """Wraps a MarketDataProvider, logging each call duration + outcome."""

    def __init__(
        self,
        inner: MarketDataProvider,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._inner = inner
        self._logger = logger or logging.getLogger(
            f"cryptozavr.providers.{inner.venue_id}"
        )
        self.venue_id = inner.venue_id

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def load_markets(self) -> None:
        await self._call("load_markets", self._inner.load_markets)

    async def fetch_ticker(self, symbol: Any) -> Any:
        return await self._call(
            "fetch_ticker", self._inner.fetch_ticker, symbol,
        )

    async def fetch_ohlcv(self, *args: Any, **kwargs: Any) -> Any:
        return await self._call(
            "fetch_ohlcv", self._inner.fetch_ohlcv, *args, **kwargs,
        )

    async def fetch_order_book(self, *args: Any, **kwargs: Any) -> Any:
        return await self._call(
            "fetch_order_book", self._inner.fetch_order_book, *args, **kwargs,
        )

    async def fetch_trades(self, *args: Any, **kwargs: Any) -> Any:
        return await self._call(
            "fetch_trades", self._inner.fetch_trades, *args, **kwargs,
        )

    async def close(self) -> None:
        await self._inner.close()

    async def _call(self, op: str, fn: Any, *args: Any, **kwargs: Any) -> Any:
        start = time.monotonic()
        self._logger.debug("%s called on %s", op, self.venue_id)
        try:
            result = await fn(*args, **kwargs)
        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            self._logger.warning(
                "%s on %s failed after %.1fms: %s",
                op, self.venue_id, duration_ms, exc,
            )
            raise
        duration_ms = (time.monotonic() - start) * 1000
        self._logger.info(
            "%s on %s succeeded in %.1fms", op, self.venue_id, duration_ms,
        )
        return result
```

- [ ] **Step 4: PASS (3 tests).**
- [ ] **Step 5: Mypy + commit**

Commit:
```text
feat(providers): add LoggingDecorator (stdlib logging)

Logs each provider call with op name, venue, duration (ms), and
outcome (succeeded/failed). DEBUG on entry, INFO on success, WARNING
on failure. Uses stdlib logging (structlog integration can be added
later via handler config, not via the decorator itself).
```

---

### Task 9: Decorator chain integration test

**Files:**
- Create: `tests/unit/infrastructure/providers/decorators/test_decorator_chain.py`

- [ ] **Step 1: Test chain composition**

Write to `tests/unit/infrastructure/providers/decorators/test_decorator_chain.py`:
```python
"""Test decorator chain composition: Logging > Caching > RateLimit > Retry > Base."""

from __future__ import annotations

import pytest

from cryptozavr.domain.exceptions import ProviderUnavailableError
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
from cryptozavr.infrastructure.providers.rate_limiters import (
    RateLimiterRegistry,
)

class _FlakyProvider:
    venue_id = "kucoin"

    def __init__(self, *, failures: int) -> None:
        self._failures = failures
        self.calls = 0

    async def fetch_ticker(self, symbol: str) -> str:
        self.calls += 1
        if self.calls <= self._failures:
            raise ProviderUnavailableError("flaky")
        return f"ticker-{symbol}"

    async def close(self) -> None:
        pass

@pytest.fixture
def rate_registry() -> RateLimiterRegistry:
    reg = RateLimiterRegistry()
    reg.register("kucoin", rate_per_sec=1000.0, capacity=10)
    return reg

@pytest.mark.asyncio
async def test_full_chain_happy_path(
    rate_registry: RateLimiterRegistry,
) -> None:
    base = _FlakyProvider(failures=0)
    chain = LoggingDecorator(
        InMemoryCachingDecorator(
            RateLimitDecorator(
                RetryDecorator(base, max_attempts=3, base_delay=0.001, jitter=0.0),
                limiter=rate_registry.get("kucoin"),
            ),
            ticker_ttl=60.0,
        ),
    )

    r1 = await chain.fetch_ticker("BTC/USDT")
    r2 = await chain.fetch_ticker("BTC/USDT")  # should hit cache
    assert r1 == "ticker-BTC/USDT"
    assert r2 == "ticker-BTC/USDT"
    assert base.calls == 1  # cache short-circuits second call

@pytest.mark.asyncio
async def test_full_chain_retries_through_flakiness(
    rate_registry: RateLimiterRegistry,
) -> None:
    base = _FlakyProvider(failures=2)
    chain = LoggingDecorator(
        InMemoryCachingDecorator(
            RateLimitDecorator(
                RetryDecorator(base, max_attempts=5, base_delay=0.001, jitter=0.0),
                limiter=rate_registry.get("kucoin"),
            ),
            ticker_ttl=60.0,
        ),
    )
    result = await chain.fetch_ticker("BTC/USDT")
    assert result == "ticker-BTC/USDT"
    assert base.calls == 3  # 2 failures + 1 success
```

- [ ] **Step 2: Run**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/infrastructure/providers/decorators/test_decorator_chain.py -v
```

Expected: 2 passed.

- [ ] **Step 3: Commit**

Commit:
```text
test(providers): add decorator chain integration test

Composes Logging > Caching > RateLimit > Retry > Base. Verifies
cache short-circuits repeat call; retry successfully navigates
transient ProviderUnavailableError through the full stack.
```

---

### Task 10: CHANGELOG + tag v0.0.5 + push

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Full verification**

```bash
cd /Users/laptop/dev/cryptozavr
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest tests/unit tests/contract -m "not integration" -v --cov=cryptozavr.infrastructure.providers --cov-report=term 2>&1 | tail -20
```

Expected: all green. Provider coverage ≥ 90%.

- [ ] **Step 2: Update CHANGELOG**

Edit `CHANGELOG.md`. Find:
```markdown
## [Unreleased]

## [0.0.4] - 2026-04-21
```

Replace with:
```markdown
## [Unreleased]

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
```

- [ ] **Step 3: Commit CHANGELOG + plan file if untracked**

```bash
cd /Users/laptop/dev/cryptozavr
git add CHANGELOG.md
git add docs/superpowers/plans/2026-04-21-cryptozavr-m2.3b-decorators-state-coingecko.md 2>/dev/null || true
```

Commit message:
```bash
docs: finalize CHANGELOG for v0.0.5 (M2.3b Decorators + State + CoinGecko)
```

- [ ] **Step 4: Tag + push**

```bash
cd /Users/laptop/dev/cryptozavr
git tag -a v0.0.5 -m "M2.3b Decorators + State + CoinGecko complete

CoinGeckoProvider (httpx) + 4 composable decorators
(Retry/RateLimit/Caching/Logging) + VenueState full State pattern
with automatic transitions. Ready for M2.3c (Chain + ProviderFactory)."

git push origin main
git push origin v0.0.5
```

- [ ] **Step 5: Summary**

```bash
cd /Users/laptop/dev/cryptozavr
echo "=== M2.3b complete ==="
git log --oneline v0.0.4..HEAD
git tag -l
```

---

## Acceptance Criteria for M2.3b

1. ✅ All 10 tasks done.
2. ✅ New tests ≥ 35 (adapter 5 + provider 6 + contract 2 + state transitions 6 + handler 4 + retry 4 + rate_limit 3 + caching 4 + logging 3 + chain 2 = ~39).
3. ✅ Mypy clean; ruff clean.
4. ✅ Provider coverage ≥ 90%.
5. ✅ `LoggingDecorator(CachingDecorator(RateLimitDecorator(RetryDecorator(provider))))` composes and works.
6. ✅ VenueState transitions: Healthy→Degraded→Healthy→RateLimited→Healthy all tested.
7. ✅ Tag `v0.0.5` on github.com/evgenygurin/cryptozavr.

---

## Notes

- **CoinGecko rate limit:** free tier = 30 req/min (~0.5 rps). When wiring `ProviderFactory` in M2.3c, register `coingecko` with `rate_per_sec=0.5, capacity=30`.
- **Clock abstraction:** caching uses `time.time()` directly so freezegun works. If we ever need per-instance Clock injection (e.g., for deterministic production monotonic), we'll add it in phase 2+ alongside the test scaffold.
- **Decorator ordering matters:** Logging outermost (sees everything including cache hits), Caching before RateLimit (cached calls don't consume tokens), RateLimit before Retry (retries share budget), Retry directly over base (retries are the lowest semantic layer).
