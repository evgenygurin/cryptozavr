# cryptozavr — Milestone 2.3a: Core Providers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Заложить основу Providers layer — `BaseProvider` (Template Method), `CCXTProvider` для KuCoin (первая concrete-реализация), `CCXTAdapter` (raw→Domain), `HttpClientRegistry` и `RateLimiterRegistry` (Singletons через DI), минимальные VenueState enums. После M2.3a: `CCXTProvider(kucoin).fetch_ticker(btc_usdt)` возвращает Domain `Ticker` через respx-mocked HTTP. Contract-тесты работают на сохранённых JSON-фикстурах без сети.

**Architecture:** Infrastructure L2. `BaseProvider` фиксирует fetch-пайплайн (ensure_markets → fetch_raw → normalize → translate_exception). `CCXTProvider` — concrete implementation использует `ccxt.async_support.kucoin()` + `CCXTAdapter` в `_normalize_*` хуках. Декораторы и Chain (полный stack) — в M2.3b/M2.3c. Этот план даёт "работающее ядро" без chain/decorators.

**Tech Stack:** Python 3.12, ccxt.async_support>=4.4, httpx>=0.27, respx>=0.21 (HTTP mocking), freezegun>=1.5 (TTL tests), asyncpg (уже установлено, не используется тут).

**Milestone position:** M2.3a of 3 sub-milestones of M2.3 of 4 milestones of MVP.

**Spec reference:** `docs/superpowers/specs/2026-04-21-cryptozavr-mvp-design.md` section 4 (Providers layer).
**Prior plans:** M1 (v0.0.1), M2.1 (v0.0.2), M2.2 (v0.0.3).
**Starting tag:** `v0.0.3`. Target: `v0.0.4`.

---

## File Structure (создаётся в M2.3a)

| Path | Responsibility |
|------|---------------|
| `src/cryptozavr/infrastructure/providers/__init__.py` | Package marker |
| `src/cryptozavr/infrastructure/providers/http.py` | `HttpClientRegistry` (one httpx.AsyncClient per venue; async context-managed) |
| `src/cryptozavr/infrastructure/providers/rate_limiters.py` | `TokenBucket` + `RateLimiterRegistry` (one bucket per venue) |
| `src/cryptozavr/infrastructure/providers/base.py` | `BaseProvider` abstract class with Template Method `_execute` |
| `src/cryptozavr/infrastructure/providers/state/__init__.py` | Package marker |
| `src/cryptozavr/infrastructure/providers/state/venue_state.py` | `VenueState` context class (minimum: holds current `VenueStateKind`; full State pattern in M2.3b) |
| `src/cryptozavr/infrastructure/providers/adapters/__init__.py` | Package marker |
| `src/cryptozavr/infrastructure/providers/adapters/ccxt_adapter.py` | `CCXTAdapter` pure static functions: `ohlcv_to_series`, `ticker_to_domain`, `orderbook_to_domain`, `trades_to_domain` |
| `src/cryptozavr/infrastructure/providers/ccxt_provider.py` | `CCXTProvider` concrete, uses `ccxt.async_support`. Implements BaseProvider hooks. |
| `tests/unit/infrastructure/providers/__init__.py` | Package marker |
| `tests/unit/infrastructure/providers/test_http_registry.py` | HttpClientRegistry lifecycle |
| `tests/unit/infrastructure/providers/test_rate_limiters.py` | TokenBucket + RateLimiterRegistry |
| `tests/unit/infrastructure/providers/test_base_provider.py` | BaseProvider `_execute` pipeline via fake subclass |
| `tests/unit/infrastructure/providers/state/__init__.py` | Package marker |
| `tests/unit/infrastructure/providers/state/test_venue_state.py` | VenueState context holds kind correctly |
| `tests/unit/infrastructure/providers/adapters/__init__.py` | Package marker |
| `tests/unit/infrastructure/providers/adapters/test_ccxt_adapter.py` | CCXTAdapter pure-fn tests on fixtures |
| `tests/contract/__init__.py` | Package marker (new) |
| `tests/contract/fixtures/kucoin/fetch_ticker_btc_usdt.json` | Saved CCXT unified ticker dict |
| `tests/contract/fixtures/kucoin/fetch_ohlcv_btc_usdt_1h.json` | Saved CCXT unified OHLCV list |
| `tests/contract/fixtures/kucoin/fetch_order_book_btc_usdt.json` | Saved CCXT unified orderbook dict |
| `tests/contract/test_kucoin_provider_contract.py` | CCXTProvider against CCXT's mocked raw responses |
| `pyproject.toml` | Add ccxt, httpx, respx, freezegun to appropriate groups |

---

## Execution Order

1. **Deps bootstrap** (Task 1) — ccxt + httpx + respx + freezegun
2. **Scaffolding** (Task 2) — package markers
3. **HttpClientRegistry** (Task 3) — TDD
4. **TokenBucket + RateLimiterRegistry** (Task 4) — TDD
5. **VenueState minimal** (Task 5) — TDD (full State pattern в M2.3b)
6. **BaseProvider Template Method** (Task 6) — TDD via fake subclass
7. **CCXTAdapter + fixtures** (Task 7) — TDD on saved JSON fixtures
8. **CCXTProvider concrete** (Task 8) — TDD with respx
9. **Contract test for KuCoin** (Task 9) — end-to-end via fixtures
10. **Full verification + tag** (Task 10)

---

## Tasks

### Task 1: Add ccxt + httpx + respx + freezegun deps

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Current state check**

```bash
cd /Users/laptop/dev/cryptozavr
grep -A 5 "^m2 = " pyproject.toml
grep -A 15 "^dev = " pyproject.toml
```

Current `m2`: asyncpg, supabase, realtime. Current `dev`: pytest+asyncio+cov+xdist, ruff, mypy, pre-commit, dirty-equals, hypothesis, polyfactory, plus m2 duplicates.

- [ ] **Step 2: Edit pyproject.toml**

Use Edit tool. Find this block:

```toml
m2 = [
    "asyncpg>=0.29",
    "supabase>=2.8",
    "realtime>=2.0",
]
```

Replace with:

```toml
m2 = [
    "asyncpg>=0.29",
    "supabase>=2.8",
    "realtime>=2.0",
    "ccxt>=4.4",
    "httpx>=0.27",
]
```

Then find the existing `dev = [...]` block. Find the last line with `"realtime>=2.0",` inside `dev` (there's a duplicate-from-m2 section). Append three new lines before the closing `]`:

```toml
    # M2.3 additions
    "ccxt>=4.4",
    "httpx>=0.27",
    "respx>=0.21",
    "freezegun>=1.5",
]
```

The resulting `dev` block should end with all four lines above added right before `]`.

- [ ] **Step 3: uv sync**

```bash
cd /Users/laptop/dev/cryptozavr
uv sync --all-extras
```

Expected: `+ ccxt==...`, `+ httpx==...`, `+ respx==...`, `+ freezegun==...` installed.

- [ ] **Step 4: Verify imports**

```bash
cd /Users/laptop/dev/cryptozavr
uv run python -c "
import ccxt.async_support as ccxt
import httpx
import respx
import freezegun
print('ok')
"
```

Expected: `ok`.

- [ ] **Step 5: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add pyproject.toml uv.lock
```

Write to `/tmp/commit-msg.txt`:
```bash
chore: add ccxt + httpx + respx + freezegun for M2.3a

ccxt.async_support for CEX integrations (KuCoin first).
httpx for CoinGecko REST (lands in M2.3b).
respx for HTTP mocking in unit/contract tests.
freezegun for TTL-sensitive tests (caching decorator in M2.3b).
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 2: Providers package scaffolding

**Files:**
- Create: `src/cryptozavr/infrastructure/providers/__init__.py`
- Create: `src/cryptozavr/infrastructure/providers/state/__init__.py`
- Create: `src/cryptozavr/infrastructure/providers/adapters/__init__.py`
- Create: `tests/unit/infrastructure/providers/__init__.py`
- Create: `tests/unit/infrastructure/providers/state/__init__.py`
- Create: `tests/unit/infrastructure/providers/adapters/__init__.py`
- Create: `tests/contract/__init__.py`
- Create: `tests/contract/fixtures/__init__.py` (if needed for pytest collection)

- [ ] **Step 1: Create src scaffolding**

Write to `src/cryptozavr/infrastructure/providers/__init__.py`:
```python
"""Providers layer: CCXT / CoinGecko integrations + decorators + chain + state.

M2.3a populates: Http/RateLimit registries, BaseProvider, CCXTAdapter, CCXTProvider.
M2.3b populates: CoinGeckoProvider, 4 decorators, VenueState full transitions.
M2.3c populates: Chain of Responsibility handlers + ProviderFactory.
"""
```

Write to `src/cryptozavr/infrastructure/providers/state/__init__.py`:
```python
"""Venue State pattern (Healthy/Degraded/RateLimited/Down)."""
```

Write to `src/cryptozavr/infrastructure/providers/adapters/__init__.py`:
```python
"""Raw → Domain adapters (pure functions)."""
```

- [ ] **Step 2: Create test scaffolding**

Create empty files (0 bytes) at:
- `tests/unit/infrastructure/providers/__init__.py`
- `tests/unit/infrastructure/providers/state/__init__.py`
- `tests/unit/infrastructure/providers/adapters/__init__.py`
- `tests/contract/__init__.py`

Also create directory `tests/contract/fixtures/kucoin/` (no `__init__.py` needed — JSON files don't need it).

```bash
mkdir -p /Users/laptop/dev/cryptozavr/tests/contract/fixtures/kucoin
```

- [ ] **Step 3: Verify imports**

```bash
cd /Users/laptop/dev/cryptozavr
uv run python -c "
import cryptozavr.infrastructure.providers
import cryptozavr.infrastructure.providers.state
import cryptozavr.infrastructure.providers.adapters
import tests.unit.infrastructure.providers
import tests.unit.infrastructure.providers.state
import tests.unit.infrastructure.providers.adapters
import tests.contract
print('ok')
"
```

Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add src/cryptozavr/infrastructure/providers tests/unit/infrastructure/providers tests/contract
```

Write to `/tmp/commit-msg.txt`:
```bash
feat(providers): scaffold providers layer package + test dirs

Adds src/cryptozavr/infrastructure/providers/ with {state,adapters}
subpackages, matching test directories, and tests/contract/ for
fixture-based API contract tests (coming in Task 7+).
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 3: HttpClientRegistry (TDD)

**Files:**
- Create: `src/cryptozavr/infrastructure/providers/http.py`
- Create: `tests/unit/infrastructure/providers/test_http_registry.py`

- [ ] **Step 1: Failing tests**

Write to `tests/unit/infrastructure/providers/test_http_registry.py`:
```python
"""Test HttpClientRegistry: one httpx.AsyncClient per venue, async lifecycle."""

from __future__ import annotations

import httpx
import pytest

from cryptozavr.infrastructure.providers.http import HttpClientRegistry

@pytest.mark.asyncio
async def test_get_returns_same_client_for_same_venue() -> None:
    registry = HttpClientRegistry()
    a = await registry.get("kucoin", base_url="https://api.kucoin.com")
    b = await registry.get("kucoin", base_url="https://api.kucoin.com")
    assert a is b
    await registry.close_all()

@pytest.mark.asyncio
async def test_get_returns_different_client_for_different_venue() -> None:
    registry = HttpClientRegistry()
    a = await registry.get("kucoin", base_url="https://api.kucoin.com")
    b = await registry.get("coingecko", base_url="https://api.coingecko.com")
    assert a is not b
    await registry.close_all()

@pytest.mark.asyncio
async def test_client_is_async() -> None:
    registry = HttpClientRegistry()
    client = await registry.get("kucoin", base_url="https://api.kucoin.com")
    assert isinstance(client, httpx.AsyncClient)
    await registry.close_all()

@pytest.mark.asyncio
async def test_close_all_closes_every_client() -> None:
    registry = HttpClientRegistry()
    await registry.get("kucoin", base_url="https://api.kucoin.com")
    await registry.get("coingecko", base_url="https://api.coingecko.com")
    await registry.close_all()

    # Attempting to get again after close gives a fresh client (re-opens).
    new_client = await registry.get("kucoin", base_url="https://api.kucoin.com")
    assert new_client is not None
    await registry.close_all()

@pytest.mark.asyncio
async def test_get_uses_default_timeout() -> None:
    registry = HttpClientRegistry(default_timeout=10.0)
    client = await registry.get("kucoin", base_url="https://api.kucoin.com")
    assert client.timeout.read == 10.0
    await registry.close_all()
```

- [ ] **Step 2: Run — FAIL**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/infrastructure/providers/test_http_registry.py -v
```

Expected: `ModuleNotFoundError: No module named 'cryptozavr.infrastructure.providers.http'`.

- [ ] **Step 3: Implement http.py**

Write to `src/cryptozavr/infrastructure/providers/http.py`:
```python
"""HttpClientRegistry: one httpx.AsyncClient per venue.

Lifecycle managed by caller (FastMCP startup/shutdown hooks in L5).
DI-singleton via composition root.
"""

from __future__ import annotations

import asyncio

import httpx

class HttpClientRegistry:
    """Keyed pool of httpx.AsyncClient instances.

    After close_all(), re-issuing get() for a venue creates a fresh client.
    """

    def __init__(self, default_timeout: float = 30.0) -> None:
        self._clients: dict[str, httpx.AsyncClient] = {}
        self._default_timeout = default_timeout
        self._lock = asyncio.Lock()

    async def get(self, venue_id: str, *, base_url: str) -> httpx.AsyncClient:
        """Return the cached client for venue_id, or create one."""
        async with self._lock:
            existing = self._clients.get(venue_id)
            if existing is not None and not existing.is_closed:
                return existing
            client = httpx.AsyncClient(
                base_url=base_url,
                timeout=self._default_timeout,
            )
            self._clients[venue_id] = client
            return client

    async def close_all(self) -> None:
        """Close every registered client and clear the registry."""
        async with self._lock:
            clients = list(self._clients.values())
            self._clients.clear()
        for client in clients:
            if not client.is_closed:
                await client.aclose()
```

- [ ] **Step 4: Run — PASS**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/infrastructure/providers/test_http_registry.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Mypy**

```bash
cd /Users/laptop/dev/cryptozavr
uv run mypy src/cryptozavr/infrastructure/providers/http.py
```

Expected: Success.

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add src/cryptozavr/infrastructure/providers/http.py tests/unit/infrastructure/providers/test_http_registry.py
```

Write to `/tmp/commit-msg.txt`:
```bash
feat(providers): add HttpClientRegistry (Singleton via DI)

One httpx.AsyncClient per venue with base_url + default_timeout.
Thread-safe via asyncio.Lock; close_all() terminates everything and
re-get() after close reopens fresh. Prepares the HTTP path for
CoinGeckoProvider in M2.3b (CCXT uses its own aiohttp internally).
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 4: TokenBucket + RateLimiterRegistry (TDD)

**Files:**
- Create: `src/cryptozavr/infrastructure/providers/rate_limiters.py`
- Create: `tests/unit/infrastructure/providers/test_rate_limiters.py`

- [ ] **Step 1: Failing tests**

Write to `tests/unit/infrastructure/providers/test_rate_limiters.py`:
```python
"""Test TokenBucket + RateLimiterRegistry."""

from __future__ import annotations

import asyncio
import time

import pytest

from cryptozavr.infrastructure.providers.rate_limiters import (
    RateLimiterRegistry,
    TokenBucket,
)

class TestTokenBucket:
    @pytest.mark.asyncio
    async def test_initial_capacity_allows_immediate_acquire(self) -> None:
        bucket = TokenBucket(rate_per_sec=10.0, capacity=5)
        start = time.monotonic()
        for _ in range(5):
            await bucket.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1  # 5 tokens available immediately

    @pytest.mark.asyncio
    async def test_exhausted_bucket_waits_for_refill(self) -> None:
        # 10 tokens/sec, capacity 2. After 2 acquires, third waits ~100ms.
        bucket = TokenBucket(rate_per_sec=10.0, capacity=2)
        await bucket.acquire()
        await bucket.acquire()
        start = time.monotonic()
        await bucket.acquire()
        elapsed = time.monotonic() - start
        # One token refills at rate 10/sec = 100ms per token.
        # Allow tolerance ±50ms for scheduling jitter.
        assert 0.05 <= elapsed <= 0.25, f"expected ~100ms, got {elapsed*1000:.0f}ms"

    @pytest.mark.asyncio
    async def test_rate_per_sec_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="rate_per_sec"):
            TokenBucket(rate_per_sec=0.0, capacity=1)

    @pytest.mark.asyncio
    async def test_capacity_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="capacity"):
            TokenBucket(rate_per_sec=1.0, capacity=0)

class TestRateLimiterRegistry:
    def test_get_returns_same_bucket_for_same_venue(self) -> None:
        registry = RateLimiterRegistry()
        registry.register("kucoin", rate_per_sec=30.0, capacity=30)
        a = registry.get("kucoin")
        b = registry.get("kucoin")
        assert a is b

    def test_get_unregistered_venue_raises(self) -> None:
        registry = RateLimiterRegistry()
        with pytest.raises(KeyError, match="kucoin"):
            registry.get("kucoin")

    def test_register_twice_for_same_venue_raises(self) -> None:
        registry = RateLimiterRegistry()
        registry.register("kucoin", rate_per_sec=30.0, capacity=30)
        with pytest.raises(ValueError, match="already registered"):
            registry.register("kucoin", rate_per_sec=10.0, capacity=10)

    def test_different_venues_get_different_buckets(self) -> None:
        registry = RateLimiterRegistry()
        registry.register("kucoin", rate_per_sec=30.0, capacity=30)
        registry.register("coingecko", rate_per_sec=0.5, capacity=30)  # 30 rpm
        assert registry.get("kucoin") is not registry.get("coingecko")
```

- [ ] **Step 2: Run — FAIL**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/infrastructure/providers/test_rate_limiters.py -v
```

- [ ] **Step 3: Implement**

Write to `src/cryptozavr/infrastructure/providers/rate_limiters.py`:
```python
"""Token bucket rate limiter + per-venue registry."""

from __future__ import annotations

import asyncio
import time

class TokenBucket:
    """Classic token bucket: `rate_per_sec` tokens added up to `capacity`.

    `acquire()` blocks until a token is available, then consumes one.
    """

    def __init__(self, *, rate_per_sec: float, capacity: int) -> None:
        if rate_per_sec <= 0:
            raise ValueError("rate_per_sec must be > 0")
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        self._rate = rate_per_sec
        self._capacity = capacity
        self._tokens: float = float(capacity)
        self._updated_at = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Block until one token is available, then consume it."""
        async with self._lock:
            while True:
                now = time.monotonic()
                delta = now - self._updated_at
                self._tokens = min(self._capacity, self._tokens + delta * self._rate)
                self._updated_at = now
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                deficit = 1 - self._tokens
                sleep_for = deficit / self._rate
                await asyncio.sleep(sleep_for)

class RateLimiterRegistry:
    """Per-venue TokenBucket registry. `register` once at startup, `get` at runtime."""

    def __init__(self) -> None:
        self._buckets: dict[str, TokenBucket] = {}

    def register(
        self, venue_id: str, *, rate_per_sec: float, capacity: int,
    ) -> None:
        """Register a bucket for venue_id. Idempotency is the caller's job."""
        if venue_id in self._buckets:
            raise ValueError(f"venue {venue_id!r} already registered")
        self._buckets[venue_id] = TokenBucket(
            rate_per_sec=rate_per_sec, capacity=capacity,
        )

    def get(self, venue_id: str) -> TokenBucket:
        """Return the bucket for venue_id or raise KeyError."""
        try:
            return self._buckets[venue_id]
        except KeyError as exc:
            raise KeyError(
                f"venue {venue_id!r} has no registered rate limiter"
            ) from exc
```

- [ ] **Step 4: Run — PASS**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/infrastructure/providers/test_rate_limiters.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Mypy**

```bash
cd /Users/laptop/dev/cryptozavr
uv run mypy src/cryptozavr/infrastructure/providers/rate_limiters.py
```

Expected: Success.

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add src/cryptozavr/infrastructure/providers/rate_limiters.py tests/unit/infrastructure/providers/test_rate_limiters.py
```

Write to `/tmp/commit-msg.txt`:
```bash
feat(providers): add TokenBucket + RateLimiterRegistry

Classic token bucket (rate_per_sec + capacity) with asyncio-safe acquire.
Registry indexed by venue_id; register once at DI wiring, get at runtime.
RateLimitDecorator in M2.3b wraps provider calls and invokes acquire().
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 5: VenueState (minimal context, TDD)

**Files:**
- Create: `src/cryptozavr/infrastructure/providers/state/venue_state.py`
- Create: `tests/unit/infrastructure/providers/state/test_venue_state.py`

M2.3a ships the minimal VenueState context sufficient for BaseProvider `require_operational`. Full State pattern (Healthy/Degraded/RateLimited/Down with transitions) lands in M2.3b.

- [ ] **Step 1: Failing tests**

Write to `tests/unit/infrastructure/providers/state/test_venue_state.py`:
```python
"""Test minimal VenueState context (M2.3a)."""

from __future__ import annotations

import pytest

from cryptozavr.domain.exceptions import ProviderUnavailableError
from cryptozavr.domain.venues import VenueId, VenueStateKind
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

class TestVenueState:
    def test_default_is_healthy(self) -> None:
        state = VenueState(venue_id=VenueId.KUCOIN)
        assert state.kind == VenueStateKind.HEALTHY
        assert state.venue_id == VenueId.KUCOIN

    def test_can_initialize_with_kind(self) -> None:
        state = VenueState(venue_id=VenueId.KUCOIN, kind=VenueStateKind.DEGRADED)
        assert state.kind == VenueStateKind.DEGRADED

    def test_require_operational_healthy_passes(self) -> None:
        state = VenueState(venue_id=VenueId.KUCOIN)
        state.require_operational()  # no raise

    def test_require_operational_degraded_passes(self) -> None:
        state = VenueState(venue_id=VenueId.KUCOIN, kind=VenueStateKind.DEGRADED)
        state.require_operational()  # degraded still operational, just flakier

    def test_require_operational_rate_limited_raises(self) -> None:
        state = VenueState(
            venue_id=VenueId.KUCOIN, kind=VenueStateKind.RATE_LIMITED,
        )
        with pytest.raises(ProviderUnavailableError, match="rate_limited"):
            state.require_operational()

    def test_require_operational_down_raises(self) -> None:
        state = VenueState(venue_id=VenueId.KUCOIN, kind=VenueStateKind.DOWN)
        with pytest.raises(ProviderUnavailableError, match="down"):
            state.require_operational()

    def test_transition_updates_kind(self) -> None:
        state = VenueState(venue_id=VenueId.KUCOIN)
        state.transition_to(VenueStateKind.DEGRADED)
        assert state.kind == VenueStateKind.DEGRADED
        state.transition_to(VenueStateKind.DOWN)
        assert state.kind == VenueStateKind.DOWN
```

- [ ] **Step 2: Run — FAIL**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/infrastructure/providers/state/test_venue_state.py -v
```

- [ ] **Step 3: Implement**

Write to `src/cryptozavr/infrastructure/providers/state/venue_state.py`:
```python
"""VenueState: minimal context for M2.3a.

Full State pattern (HealthyState/DegradedState/RateLimitedState/DownState classes
with on_request_succeeded / on_request_failed transitions) arrives in M2.3b.
"""

from __future__ import annotations

from cryptozavr.domain.exceptions import ProviderUnavailableError
from cryptozavr.domain.venues import VenueId, VenueStateKind

class VenueState:
    """Tracks a venue's operational state. Used by BaseProvider._execute."""

    def __init__(
        self,
        venue_id: VenueId,
        *,
        kind: VenueStateKind = VenueStateKind.HEALTHY,
    ) -> None:
        self.venue_id = venue_id
        self._kind = kind

    @property
    def kind(self) -> VenueStateKind:
        return self._kind

    def transition_to(self, new_kind: VenueStateKind) -> None:
        """Force-transition to a new state. M2.3b adds transition rules."""
        self._kind = new_kind

    def require_operational(self) -> None:
        """Raise ProviderUnavailableError if the venue is not usable."""
        if self._kind == VenueStateKind.RATE_LIMITED:
            raise ProviderUnavailableError(
                f"venue {self.venue_id.value} is rate_limited"
            )
        if self._kind == VenueStateKind.DOWN:
            raise ProviderUnavailableError(
                f"venue {self.venue_id.value} is down"
            )
        # HEALTHY and DEGRADED are considered operational.
```

- [ ] **Step 4: Run — PASS**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/infrastructure/providers/state/test_venue_state.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Mypy**

```bash
cd /Users/laptop/dev/cryptozavr
uv run mypy src/cryptozavr/infrastructure/providers/state/venue_state.py
```

Expected: Success.

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add src/cryptozavr/infrastructure/providers/state/venue_state.py tests/unit/infrastructure/providers/state/test_venue_state.py
```

Write to `/tmp/commit-msg.txt`:
```bash
feat(providers): add minimal VenueState context

Holds current VenueStateKind + require_operational guard (raises
ProviderUnavailableError for RATE_LIMITED/DOWN). Full State pattern
with automatic transitions lands in M2.3b alongside RateLimitDecorator.
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 6: BaseProvider Template Method (TDD)

**Files:**
- Create: `src/cryptozavr/infrastructure/providers/base.py`
- Create: `tests/unit/infrastructure/providers/test_base_provider.py`

- [ ] **Step 1: Failing tests**

Write to `tests/unit/infrastructure/providers/test_base_provider.py`:
```python
"""Test BaseProvider Template Method via fake subclass."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pytest

from cryptozavr.domain.exceptions import (
    ProviderUnavailableError,
    RateLimitExceededError,
)
from cryptozavr.domain.market_data import Ticker
from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant
from cryptozavr.domain.venues import MarketType, VenueId, VenueStateKind
from cryptozavr.infrastructure.providers.base import BaseProvider
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

@dataclass
class _FakeRawTicker:
    raw_last: str = "1.0"

class _FakeProvider(BaseProvider):
    """Minimal concrete subclass for pipeline testing."""

    def __init__(
        self,
        venue_id: VenueId,
        state: VenueState,
        *,
        ensure_markets_raises: Exception | None = None,
        fetch_ticker_raises: Exception | None = None,
    ) -> None:
        super().__init__(venue_id=venue_id, state=state)
        self.ensure_markets_called = 0
        self.fetch_ticker_called = 0
        self._ensure_markets_raises = ensure_markets_raises
        self._fetch_ticker_raises = fetch_ticker_raises

    async def _ensure_markets_loaded(self) -> None:
        self.ensure_markets_called += 1
        if self._ensure_markets_raises:
            raise self._ensure_markets_raises

    async def _fetch_ticker_raw(self, symbol: object) -> _FakeRawTicker:
        self.fetch_ticker_called += 1
        if self._fetch_ticker_raises:
            raise self._fetch_ticker_raises
        return _FakeRawTicker()

    def _normalize_ticker(self, raw: _FakeRawTicker, symbol: object) -> Ticker:
        return Ticker(
            symbol=symbol,  # type: ignore[arg-type]
            last=Decimal(raw.raw_last),
            observed_at=Instant.now(),
            quality=DataQuality(
                source=Provenance(
                    venue_id=self.venue_id.value, endpoint="fetch_ticker",
                ),
                fetched_at=Instant.now(),
                staleness=Staleness.FRESH,
                confidence=Confidence.HIGH,
                cache_hit=False,
            ),
        )

    def _translate_exception(self, exc: Exception) -> Exception:
        return exc

@pytest.fixture
def registry() -> SymbolRegistry:
    return SymbolRegistry()

@pytest.fixture
def btc_symbol(registry: SymbolRegistry) -> Any:
    return registry.get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )

@pytest.mark.asyncio
async def test_fetch_ticker_happy_path(btc_symbol: Any) -> None:
    state = VenueState(VenueId.KUCOIN)
    provider = _FakeProvider(VenueId.KUCOIN, state)
    ticker = await provider.fetch_ticker(btc_symbol)
    assert ticker.last == Decimal("1.0")
    assert provider.ensure_markets_called == 1
    assert provider.fetch_ticker_called == 1

@pytest.mark.asyncio
async def test_fetch_ticker_rejects_when_venue_down(btc_symbol: Any) -> None:
    state = VenueState(VenueId.KUCOIN, kind=VenueStateKind.DOWN)
    provider = _FakeProvider(VenueId.KUCOIN, state)
    with pytest.raises(ProviderUnavailableError):
        await provider.fetch_ticker(btc_symbol)
    # ensure_markets should NOT be called — require_operational is first.
    assert provider.ensure_markets_called == 0

@pytest.mark.asyncio
async def test_fetch_ticker_ensures_markets_loaded_only_once(btc_symbol: Any) -> None:
    state = VenueState(VenueId.KUCOIN)
    provider = _FakeProvider(VenueId.KUCOIN, state)
    await provider.fetch_ticker(btc_symbol)
    await provider.fetch_ticker(btc_symbol)
    # BaseProvider caches 'markets loaded' flag — subclass's
    # _ensure_markets_loaded is called multiple times but internally
    # the subclass decides whether to re-load. Here we verify that
    # Template Method invokes the hook every time (BaseProvider doesn't
    # memoize; that's subclass's job).
    assert provider.ensure_markets_called == 2

@pytest.mark.asyncio
async def test_fetch_ticker_translates_raw_exception(btc_symbol: Any) -> None:
    state = VenueState(VenueId.KUCOIN)

    class _CustomProvider(_FakeProvider):
        def _translate_exception(self, exc: Exception) -> Exception:
            if isinstance(exc, ValueError):
                return RateLimitExceededError("rate limit hit")
            return exc

    raw_exc = ValueError("429 too many requests")
    provider = _CustomProvider(
        VenueId.KUCOIN, state, fetch_ticker_raises=raw_exc,
    )
    with pytest.raises(RateLimitExceededError, match="rate limit hit"):
        await provider.fetch_ticker(btc_symbol)
```

- [ ] **Step 2: Run — FAIL**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/infrastructure/providers/test_base_provider.py -v
```

- [ ] **Step 3: Implement**

Write to `src/cryptozavr/infrastructure/providers/base.py`:
```python
"""BaseProvider: Template Method for provider fetch operations.

Subclasses override the abstract hooks; the skeleton (_execute) stays fixed:
  1. state.require_operational()
  2. _ensure_markets_loaded()
  3. _fetch_*_raw()
  4. _normalize_*()
  5. catch → _translate_exception()
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from cryptozavr.domain.interfaces import MarketDataProvider
from cryptozavr.domain.market_data import (
    OHLCVSeries,
    OrderBookSnapshot,
    Ticker,
    TradeTick,
)
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Instant, Timeframe
from cryptozavr.domain.venues import VenueId
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

class BaseProvider(ABC, MarketDataProvider):
    """Template Method skeleton for Domain MarketDataProvider implementations."""

    def __init__(self, *, venue_id: VenueId, state: VenueState) -> None:
        self.venue_id = venue_id
        self._state = state

    # ---- Public MarketDataProvider interface ----

    async def load_markets(self) -> None:
        await self._ensure_markets_loaded()

    async def fetch_ticker(self, symbol: Symbol) -> Ticker:
        return await self._execute_ticker(symbol)

    async def fetch_ohlcv(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        since: Instant | None = None,
        limit: int = 500,
    ) -> OHLCVSeries:
        return await self._execute_ohlcv(symbol, timeframe, since, limit)

    async def fetch_order_book(
        self, symbol: Symbol, depth: int = 50,
    ) -> OrderBookSnapshot:
        return await self._execute_orderbook(symbol, depth)

    async def fetch_trades(
        self,
        symbol: Symbol,
        since: Instant | None = None,
        limit: int = 100,
    ) -> tuple[TradeTick, ...]:
        return await self._execute_trades(symbol, since, limit)

    async def close(self) -> None:
        """Default no-op. Override if the underlying client needs closing."""
        return None

    # ---- Template Method: ticker/ohlcv/orderbook/trades execution ----

    async def _execute_ticker(self, symbol: Symbol) -> Ticker:
        self._state.require_operational()
        try:
            await self._ensure_markets_loaded()
            raw = await self._fetch_ticker_raw(symbol)
        except Exception as exc:
            raise self._translate_exception(exc) from exc
        return self._normalize_ticker(raw, symbol)

    async def _execute_ohlcv(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        since: Instant | None,
        limit: int,
    ) -> OHLCVSeries:
        self._state.require_operational()
        try:
            await self._ensure_markets_loaded()
            raw = await self._fetch_ohlcv_raw(symbol, timeframe, since, limit)
        except Exception as exc:
            raise self._translate_exception(exc) from exc
        return self._normalize_ohlcv(raw, symbol, timeframe)

    async def _execute_orderbook(
        self, symbol: Symbol, depth: int,
    ) -> OrderBookSnapshot:
        self._state.require_operational()
        try:
            await self._ensure_markets_loaded()
            raw = await self._fetch_order_book_raw(symbol, depth)
        except Exception as exc:
            raise self._translate_exception(exc) from exc
        return self._normalize_order_book(raw, symbol)

    async def _execute_trades(
        self,
        symbol: Symbol,
        since: Instant | None,
        limit: int,
    ) -> tuple[TradeTick, ...]:
        self._state.require_operational()
        try:
            await self._ensure_markets_loaded()
            raw = await self._fetch_trades_raw(symbol, since, limit)
        except Exception as exc:
            raise self._translate_exception(exc) from exc
        return self._normalize_trades(raw, symbol)

    # ---- Abstract hooks (subclass overrides) ----

    @abstractmethod
    async def _ensure_markets_loaded(self) -> None: ...

    @abstractmethod
    async def _fetch_ticker_raw(self, symbol: Symbol) -> Any: ...

    @abstractmethod
    def _normalize_ticker(self, raw: Any, symbol: Symbol) -> Ticker: ...

    async def _fetch_ohlcv_raw(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        since: Instant | None,
        limit: int,
    ) -> Any:
        raise NotImplementedError("ohlcv not implemented for this provider")

    def _normalize_ohlcv(
        self, raw: Any, symbol: Symbol, timeframe: Timeframe,
    ) -> OHLCVSeries:
        raise NotImplementedError("ohlcv not implemented for this provider")

    async def _fetch_order_book_raw(self, symbol: Symbol, depth: int) -> Any:
        raise NotImplementedError("order_book not implemented for this provider")

    def _normalize_order_book(
        self, raw: Any, symbol: Symbol,
    ) -> OrderBookSnapshot:
        raise NotImplementedError("order_book not implemented for this provider")

    async def _fetch_trades_raw(
        self, symbol: Symbol, since: Instant | None, limit: int,
    ) -> Any:
        raise NotImplementedError("trades not implemented for this provider")

    def _normalize_trades(
        self, raw: Any, symbol: Symbol,
    ) -> tuple[TradeTick, ...]:
        raise NotImplementedError("trades not implemented for this provider")

    @abstractmethod
    def _translate_exception(self, exc: Exception) -> Exception: ...
```

- [ ] **Step 4: Run — PASS**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/infrastructure/providers/test_base_provider.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Mypy**

```bash
cd /Users/laptop/dev/cryptozavr
uv run mypy src/cryptozavr/infrastructure/providers/base.py
```

Expected: Success.

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add src/cryptozavr/infrastructure/providers/base.py tests/unit/infrastructure/providers/test_base_provider.py
```

Write to `/tmp/commit-msg.txt`:
```bash
feat(providers): add BaseProvider Template Method

Skeleton: require_operational → ensure_markets → fetch_raw → normalize,
with _translate_exception in catch. Four flavours (ticker/ohlcv/orderbook/
trades) share the same pipeline. ohlcv/orderbook/trades raw+normalize
hooks default to NotImplementedError so partial-impl providers work
(e.g. CoinGecko in M2.3b skips orderbook).
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 7: CCXTAdapter + contract fixtures (TDD)

**Files:**
- Create: `src/cryptozavr/infrastructure/providers/adapters/ccxt_adapter.py`
- Create: `tests/unit/infrastructure/providers/adapters/test_ccxt_adapter.py`
- Create: `tests/contract/fixtures/kucoin/fetch_ticker_btc_usdt.json`
- Create: `tests/contract/fixtures/kucoin/fetch_ohlcv_btc_usdt_1h.json`
- Create: `tests/contract/fixtures/kucoin/fetch_order_book_btc_usdt.json`

- [ ] **Step 1: Write fixture JSON files**

Write to `tests/contract/fixtures/kucoin/fetch_ticker_btc_usdt.json`:
```json
{
  "symbol": "BTC/USDT",
  "timestamp": 1745200800000,
  "datetime": "2026-04-21T10:00:00.000Z",
  "high": 66000.0,
  "low": 64000.0,
  "bid": 64999.5,
  "bidVolume": 1.0,
  "ask": 65001.5,
  "askVolume": 0.5,
  "vwap": 65000.0,
  "open": 63400.0,
  "close": 65000.5,
  "last": 65000.5,
  "previousClose": 63400.0,
  "change": 1600.5,
  "percentage": 2.524,
  "average": 64200.25,
  "baseVolume": 1234.56,
  "quoteVolume": 80246412.34,
  "info": {}
}
```

Write to `tests/contract/fixtures/kucoin/fetch_ohlcv_btc_usdt_1h.json`:
```json
[
  [1745200800000, 64000.0, 64500.0, 63900.0, 64200.0, 120.5],
  [1745204400000, 64200.0, 64800.0, 64100.0, 64700.0, 135.2],
  [1745208000000, 64700.0, 65100.0, 64600.0, 65000.5, 142.8],
  [1745211600000, 65000.5, 65300.0, 64900.0, 65100.0, 98.3],
  [1745215200000, 65100.0, 65400.0, 65000.0, 65200.0, 110.7]
]
```

Write to `tests/contract/fixtures/kucoin/fetch_order_book_btc_usdt.json`:
```json
{
  "symbol": "BTC/USDT",
  "timestamp": 1745200800000,
  "datetime": "2026-04-21T10:00:00.000Z",
  "nonce": 123456789,
  "bids": [
    [64999.5, 1.0],
    [64999.0, 2.5],
    [64998.5, 0.75]
  ],
  "asks": [
    [65001.5, 0.5],
    [65002.0, 1.25],
    [65002.5, 3.0]
  ]
}
```

- [ ] **Step 2: Failing tests**

Write to `tests/unit/infrastructure/providers/adapters/test_ccxt_adapter.py`:
```python
"""Test CCXTAdapter pure functions on saved unified-format fixtures."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Timeframe
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.adapters.ccxt_adapter import CCXTAdapter

FIXTURE_DIR = (
    Path(__file__).resolve().parents[4] / "contract" / "fixtures" / "kucoin"
)

@pytest.fixture
def registry() -> SymbolRegistry:
    return SymbolRegistry()

@pytest.fixture
def btc_symbol(registry: SymbolRegistry):
    return registry.get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )

@pytest.fixture
def ticker_raw() -> dict:
    return json.loads((FIXTURE_DIR / "fetch_ticker_btc_usdt.json").read_text())

@pytest.fixture
def ohlcv_raw() -> list:
    return json.loads((FIXTURE_DIR / "fetch_ohlcv_btc_usdt_1h.json").read_text())

@pytest.fixture
def orderbook_raw() -> dict:
    return json.loads(
        (FIXTURE_DIR / "fetch_order_book_btc_usdt.json").read_text()
    )

class TestTickerToDomain:
    def test_happy_path(self, btc_symbol, ticker_raw: dict) -> None:
        ticker = CCXTAdapter.ticker_to_domain(ticker_raw, btc_symbol)
        assert ticker.symbol is btc_symbol
        assert ticker.last == Decimal("65000.5")
        assert ticker.bid == Decimal("64999.5")
        assert ticker.ask == Decimal("65001.5")
        assert ticker.volume_24h == Decimal("1234.56")
        assert ticker.high_24h == Decimal("66000.0")
        assert ticker.low_24h == Decimal("64000.0")
        assert ticker.change_24h_pct is not None
        assert ticker.change_24h_pct.value == Decimal("2.524")
        assert ticker.observed_at == Instant.from_ms(1_745_200_800_000)
        assert ticker.quality.source.venue_id == "kucoin"
        assert ticker.quality.source.endpoint == "fetch_ticker"

    def test_missing_bid_ask_returns_none(self, btc_symbol) -> None:
        partial = {
            "symbol": "BTC/USDT",
            "timestamp": 1745200800000,
            "last": 65000.5,
        }
        ticker = CCXTAdapter.ticker_to_domain(partial, btc_symbol)
        assert ticker.bid is None
        assert ticker.ask is None

class TestOhlcvToSeries:
    def test_happy_path(self, btc_symbol, ohlcv_raw: list) -> None:
        series = CCXTAdapter.ohlcv_to_series(
            ohlcv_raw, btc_symbol, Timeframe.H1,
        )
        assert len(series.candles) == 5
        assert series.symbol is btc_symbol
        assert series.timeframe == Timeframe.H1
        first = series.candles[0]
        assert first.opened_at == Instant.from_ms(1_745_200_800_000)
        assert first.open == Decimal("64000.0")
        assert first.high == Decimal("64500.0")
        assert first.low == Decimal("63900.0")
        assert first.close == Decimal("64200.0")
        assert first.volume == Decimal("120.5")

    def test_empty_list_raises(self, btc_symbol) -> None:
        with pytest.raises(ValueError, match="empty"):
            CCXTAdapter.ohlcv_to_series([], btc_symbol, Timeframe.H1)

class TestOrderBookToDomain:
    def test_happy_path(self, btc_symbol, orderbook_raw: dict) -> None:
        ob = CCXTAdapter.orderbook_to_domain(orderbook_raw, btc_symbol)
        assert len(ob.bids) == 3
        assert len(ob.asks) == 3
        assert ob.bids[0].price == Decimal("64999.5")
        assert ob.bids[0].size == Decimal("1.0")
        assert ob.asks[0].price == Decimal("65001.5")
        assert ob.asks[0].size == Decimal("0.5")
        assert ob.observed_at == Instant.from_ms(1_745_200_800_000)
```

- [ ] **Step 3: Run — FAIL**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/infrastructure/providers/adapters/test_ccxt_adapter.py -v
```

- [ ] **Step 4: Implement ccxt_adapter.py**

Write to `src/cryptozavr/infrastructure/providers/adapters/ccxt_adapter.py`:
```python
"""CCXTAdapter: raw CCXT unified dict → Domain entities.

Pure functions. No I/O. Ideal for property-based tests on saved fixtures.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from cryptozavr.domain.market_data import (
    OHLCVCandle,
    OHLCVSeries,
    OrderBookSnapshot,
    Ticker,
)
from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import (
    Instant,
    Percentage,
    PriceSize,
    Timeframe,
    TimeRange,
)

class CCXTAdapter:
    """Static conversions from CCXT unified format to Domain entities."""

    @staticmethod
    def ticker_to_domain(raw: Mapping[str, Any], symbol: Symbol) -> Ticker:
        """Map a CCXT unified ticker dict to Domain Ticker."""
        observed_ms = int(raw.get("timestamp") or 0)
        observed_at = Instant.from_ms(observed_ms) if observed_ms else Instant.now()
        quality = _fresh_quality(symbol, endpoint="fetch_ticker")
        return Ticker(
            symbol=symbol,
            last=_decimal(raw["last"]),
            observed_at=observed_at,
            quality=quality,
            bid=_optional_decimal(raw.get("bid")),
            ask=_optional_decimal(raw.get("ask")),
            volume_24h=_optional_decimal(raw.get("baseVolume")),
            change_24h_pct=(
                Percentage(value=_decimal(raw["percentage"]))
                if raw.get("percentage") is not None else None
            ),
            high_24h=_optional_decimal(raw.get("high")),
            low_24h=_optional_decimal(raw.get("low")),
        )

    @staticmethod
    def ohlcv_to_series(
        raw: Sequence[Sequence[Any]],
        symbol: Symbol,
        timeframe: Timeframe,
    ) -> OHLCVSeries:
        """Map CCXT unified OHLCV (list of [ts, o, h, l, c, v]) to OHLCVSeries."""
        if not raw:
            raise ValueError("ohlcv_to_series received an empty list")
        candles = tuple(
            OHLCVCandle(
                opened_at=Instant.from_ms(int(row[0])),
                open=_decimal(row[1]),
                high=_decimal(row[2]),
                low=_decimal(row[3]),
                close=_decimal(row[4]),
                volume=_decimal(row[5]),
                closed=True,
            )
            for row in raw
        )
        tf_ms = timeframe.to_milliseconds()
        last_ms = candles[-1].opened_at.to_ms()
        series_range = TimeRange(
            start=candles[0].opened_at,
            end=Instant.from_ms(last_ms + tf_ms),
        )
        return OHLCVSeries(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
            range=series_range,
            quality=_fresh_quality(symbol, endpoint="fetch_ohlcv"),
        )

    @staticmethod
    def orderbook_to_domain(
        raw: Mapping[str, Any], symbol: Symbol,
    ) -> OrderBookSnapshot:
        """Map CCXT unified orderbook dict to OrderBookSnapshot."""
        observed_ms = int(raw.get("timestamp") or 0)
        observed_at = Instant.from_ms(observed_ms) if observed_ms else Instant.now()
        bids = tuple(
            PriceSize(price=_decimal(level[0]), size=_decimal(level[1]))
            for level in raw.get("bids", [])
        )
        asks = tuple(
            PriceSize(price=_decimal(level[0]), size=_decimal(level[1]))
            for level in raw.get("asks", [])
        )
        return OrderBookSnapshot(
            symbol=symbol,
            bids=bids,
            asks=asks,
            observed_at=observed_at,
            quality=_fresh_quality(symbol, endpoint="fetch_order_book"),
        )

def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))

def _optional_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))

def _fresh_quality(symbol: Symbol, *, endpoint: str) -> DataQuality:
    return DataQuality(
        source=Provenance(venue_id=symbol.venue.value, endpoint=endpoint),
        fetched_at=Instant.now(),
        staleness=Staleness.FRESH,
        confidence=Confidence.HIGH,
        cache_hit=False,
    )
```

- [ ] **Step 5: Run — PASS**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/infrastructure/providers/adapters/test_ccxt_adapter.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Mypy + Commit**

```bash
cd /Users/laptop/dev/cryptozavr
uv run mypy src/cryptozavr/infrastructure/providers/adapters/ccxt_adapter.py
```

Expected: Success.

```bash
cd /Users/laptop/dev/cryptozavr
git add \
  src/cryptozavr/infrastructure/providers/adapters/ccxt_adapter.py \
  tests/unit/infrastructure/providers/adapters/test_ccxt_adapter.py \
  tests/contract/fixtures/kucoin/fetch_ticker_btc_usdt.json \
  tests/contract/fixtures/kucoin/fetch_ohlcv_btc_usdt_1h.json \
  tests/contract/fixtures/kucoin/fetch_order_book_btc_usdt.json
```

Write to `/tmp/commit-msg.txt`:
```bash
feat(providers): add CCXTAdapter + kucoin fixtures

Static conversions ticker/ohlcv/orderbook CCXT unified → Domain.
Fixtures: tiny hand-written BTC/USDT samples (3-5 rows each) for
contract tests. Decimals throughout; timestamp -> Instant.from_ms;
missing optional fields handled.
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 8: CCXTProvider concrete (TDD with fake exchange)

**Files:**
- Create: `src/cryptozavr/infrastructure/providers/ccxt_provider.py`
- Create: `tests/unit/infrastructure/providers/test_ccxt_provider.py`

CCXT's `ccxt.kucoin()` connects live. Unit test uses a **fake exchange object** injected via constructor; no respx needed at this level.

- [ ] **Step 1: Failing tests**

Write to `tests/unit/infrastructure/providers/test_ccxt_provider.py`:
```python
"""Test CCXTProvider with fake exchange (no network)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import ccxt.async_support as ccxt_async
import pytest

from cryptozavr.domain.exceptions import (
    ProviderUnavailableError,
    RateLimitExceededError,
)
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.ccxt_provider import CCXTProvider
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

FIXTURE_DIR = (
    Path(__file__).resolve().parents[3] / "contract" / "fixtures" / "kucoin"
)

class _FakeExchange:
    """Minimal CCXT exchange duck-type for tests."""

    def __init__(
        self,
        *,
        ticker: dict | None = None,
        ohlcv: list | None = None,
        order_book: dict | None = None,
        load_markets_raises: Exception | None = None,
        ticker_raises: Exception | None = None,
    ) -> None:
        self._ticker = ticker
        self._ohlcv = ohlcv
        self._order_book = order_book
        self._load_markets_raises = load_markets_raises
        self._ticker_raises = ticker_raises
        self.load_markets_called = 0
        self.closed = False

    async def load_markets(self) -> dict:
        self.load_markets_called += 1
        if self._load_markets_raises:
            raise self._load_markets_raises
        return {}

    async def fetch_ticker(self, symbol: str) -> dict:
        if self._ticker_raises:
            raise self._ticker_raises
        assert self._ticker is not None
        return self._ticker

    async def fetch_ohlcv(
        self, symbol: str, timeframe: str,
        since: int | None = None, limit: int = 500,
    ) -> list:
        assert self._ohlcv is not None
        return self._ohlcv

    async def fetch_order_book(self, symbol: str, limit: int = 50) -> dict:
        assert self._order_book is not None
        return self._order_book

    async def close(self) -> None:
        self.closed = True

@pytest.fixture
def registry() -> SymbolRegistry:
    return SymbolRegistry()

@pytest.fixture
def btc_symbol(registry: SymbolRegistry):
    return registry.get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )

@pytest.fixture
def ticker_fix() -> dict:
    return json.loads((FIXTURE_DIR / "fetch_ticker_btc_usdt.json").read_text())

@pytest.fixture
def ohlcv_fix() -> list:
    return json.loads((FIXTURE_DIR / "fetch_ohlcv_btc_usdt_1h.json").read_text())

@pytest.fixture
def ob_fix() -> dict:
    return json.loads(
        (FIXTURE_DIR / "fetch_order_book_btc_usdt.json").read_text()
    )

@pytest.mark.asyncio
async def test_fetch_ticker_happy_path(btc_symbol, ticker_fix: dict) -> None:
    fake = _FakeExchange(ticker=ticker_fix)
    provider = CCXTProvider(
        venue_id=VenueId.KUCOIN,
        state=VenueState(VenueId.KUCOIN),
        exchange=fake,
    )
    ticker = await provider.fetch_ticker(btc_symbol)
    assert ticker.last == Decimal("65000.5")
    assert fake.load_markets_called == 1

@pytest.mark.asyncio
async def test_fetch_ohlcv_happy_path(btc_symbol, ohlcv_fix: list) -> None:
    fake = _FakeExchange(ohlcv=ohlcv_fix)
    provider = CCXTProvider(
        venue_id=VenueId.KUCOIN,
        state=VenueState(VenueId.KUCOIN),
        exchange=fake,
    )
    series = await provider.fetch_ohlcv(btc_symbol, Timeframe.H1, limit=5)
    assert len(series.candles) == 5

@pytest.mark.asyncio
async def test_fetch_order_book_happy_path(btc_symbol, ob_fix: dict) -> None:
    fake = _FakeExchange(order_book=ob_fix)
    provider = CCXTProvider(
        venue_id=VenueId.KUCOIN,
        state=VenueState(VenueId.KUCOIN),
        exchange=fake,
    )
    ob = await provider.fetch_order_book(btc_symbol, depth=3)
    assert len(ob.bids) == 3
    assert len(ob.asks) == 3

@pytest.mark.asyncio
async def test_rate_limit_exception_translated(btc_symbol) -> None:
    fake = _FakeExchange(
        ticker_raises=ccxt_async.RateLimitExceeded("429 Too Many Requests"),
    )
    provider = CCXTProvider(
        venue_id=VenueId.KUCOIN,
        state=VenueState(VenueId.KUCOIN),
        exchange=fake,
    )
    with pytest.raises(RateLimitExceededError):
        await provider.fetch_ticker(btc_symbol)

@pytest.mark.asyncio
async def test_network_exception_translated(btc_symbol) -> None:
    fake = _FakeExchange(
        ticker_raises=ccxt_async.NetworkError("connection refused"),
    )
    provider = CCXTProvider(
        venue_id=VenueId.KUCOIN,
        state=VenueState(VenueId.KUCOIN),
        exchange=fake,
    )
    with pytest.raises(ProviderUnavailableError):
        await provider.fetch_ticker(btc_symbol)

@pytest.mark.asyncio
async def test_close_closes_exchange(btc_symbol, ticker_fix: dict) -> None:
    fake = _FakeExchange(ticker=ticker_fix)
    provider = CCXTProvider(
        venue_id=VenueId.KUCOIN,
        state=VenueState(VenueId.KUCOIN),
        exchange=fake,
    )
    await provider.close()
    assert fake.closed is True

@pytest.mark.asyncio
async def test_markets_loaded_only_once(btc_symbol, ticker_fix: dict) -> None:
    fake = _FakeExchange(ticker=ticker_fix)
    provider = CCXTProvider(
        venue_id=VenueId.KUCOIN,
        state=VenueState(VenueId.KUCOIN),
        exchange=fake,
    )
    await provider.fetch_ticker(btc_symbol)
    await provider.fetch_ticker(btc_symbol)
    await provider.fetch_ticker(btc_symbol)
    assert fake.load_markets_called == 1
```

- [ ] **Step 2: Run — FAIL**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/infrastructure/providers/test_ccxt_provider.py -v
```

- [ ] **Step 3: Implement**

Write to `src/cryptozavr/infrastructure/providers/ccxt_provider.py`:
```python
"""CCXTProvider: concrete BaseProvider using ccxt.async_support."""

from __future__ import annotations

from typing import Any, Protocol

import ccxt.async_support as ccxt_async

from cryptozavr.domain.exceptions import (
    ProviderUnavailableError,
    RateLimitExceededError,
)
from cryptozavr.domain.market_data import (
    OHLCVSeries,
    OrderBookSnapshot,
    Ticker,
)
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Instant, Timeframe
from cryptozavr.domain.venues import VenueId
from cryptozavr.infrastructure.providers.adapters.ccxt_adapter import CCXTAdapter
from cryptozavr.infrastructure.providers.base import BaseProvider
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

class _ExchangeProtocol(Protocol):
    """Duck-type matching ccxt.async_support.Exchange subset we use."""

    async def load_markets(self) -> Any: ...
    async def fetch_ticker(self, symbol: str) -> Any: ...
    async def fetch_ohlcv(
        self, symbol: str, timeframe: str,
        since: int | None = ..., limit: int = ...,
    ) -> Any: ...
    async def fetch_order_book(self, symbol: str, limit: int = ...) -> Any: ...
    async def close(self) -> Any: ...

class CCXTProvider(BaseProvider):
    """CCXT-powered provider. Works with any CCXT exchange (start with kucoin)."""

    def __init__(
        self,
        *,
        venue_id: VenueId,
        state: VenueState,
        exchange: _ExchangeProtocol,
    ) -> None:
        super().__init__(venue_id=venue_id, state=state)
        self._exchange = exchange
        self._markets_loaded = False

    @classmethod
    def for_kucoin(
        cls, *, state: VenueState, **ccxt_opts: Any,
    ) -> CCXTProvider:
        """Factory helper: build a CCXTProvider wrapping ccxt.kucoin()."""
        exchange = ccxt_async.kucoin({**ccxt_opts, "enableRateLimit": False})
        return cls(
            venue_id=VenueId.KUCOIN, state=state, exchange=exchange,
        )

    # ---- BaseProvider hooks ----

    async def _ensure_markets_loaded(self) -> None:
        if not self._markets_loaded:
            await self._exchange.load_markets()
            self._markets_loaded = True

    async def _fetch_ticker_raw(self, symbol: Symbol) -> Any:
        return await self._exchange.fetch_ticker(symbol.native_symbol)

    def _normalize_ticker(self, raw: Any, symbol: Symbol) -> Ticker:
        return CCXTAdapter.ticker_to_domain(raw, symbol)

    async def _fetch_ohlcv_raw(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        since: Instant | None,
        limit: int,
    ) -> Any:
        return await self._exchange.fetch_ohlcv(
            symbol.native_symbol,
            timeframe.to_ccxt_string(),
            since=since.to_ms() if since else None,
            limit=limit,
        )

    def _normalize_ohlcv(
        self, raw: Any, symbol: Symbol, timeframe: Timeframe,
    ) -> OHLCVSeries:
        return CCXTAdapter.ohlcv_to_series(raw, symbol, timeframe)

    async def _fetch_order_book_raw(self, symbol: Symbol, depth: int) -> Any:
        return await self._exchange.fetch_order_book(
            symbol.native_symbol, limit=depth,
        )

    def _normalize_order_book(
        self, raw: Any, symbol: Symbol,
    ) -> OrderBookSnapshot:
        return CCXTAdapter.orderbook_to_domain(raw, symbol)

    def _translate_exception(self, exc: Exception) -> Exception:
        if isinstance(exc, ccxt_async.RateLimitExceeded):
            return RateLimitExceededError(str(exc))
        if isinstance(exc, ccxt_async.NetworkError):
            return ProviderUnavailableError(str(exc))
        return exc

    async def close(self) -> None:
        await self._exchange.close()
```

- [ ] **Step 4: Run — PASS**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/infrastructure/providers/test_ccxt_provider.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Mypy**

```bash
cd /Users/laptop/dev/cryptozavr
uv run mypy src/cryptozavr/infrastructure/providers/ccxt_provider.py
```

Expected: Success. If ccxt lacks type stubs, add a module-level override in pyproject.toml:

```toml
[[tool.mypy.overrides]]
module = "ccxt.*"
ignore_missing_imports = true
```

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add src/cryptozavr/infrastructure/providers/ccxt_provider.py tests/unit/infrastructure/providers/test_ccxt_provider.py
# include pyproject.toml if mypy override was needed
git add pyproject.toml 2>/dev/null || true
```

Write to `/tmp/commit-msg.txt`:
```bash
feat(providers): add CCXTProvider (BaseProvider + CCXTAdapter)

Concrete provider using ccxt.async_support; fetch_ticker/ohlcv/orderbook
wired to CCXT methods and adapted via CCXTAdapter. Exception translation:
CCXT.RateLimitExceeded → RateLimitExceededError; CCXT.NetworkError →
ProviderUnavailableError. Markets loaded lazily, cached in-memory.
for_kucoin() classmethod as convenience factory for DI.
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 9: KuCoin contract test (fixture-driven, no network)

**Files:**
- Create: `tests/contract/test_kucoin_provider_contract.py`

This test wires CCXTProvider with the fake exchange, feeds fixtures, and asserts the full path (BaseProvider → CCXTAdapter → Domain) works end-to-end without duplicating adapter-level asserts.

- [ ] **Step 1: Write test**

Write to `tests/contract/test_kucoin_provider_contract.py`:
```python
"""Contract tests: CCXTProvider against saved KuCoin fixtures.

Marker: @pytest.mark.contract. Runs without network.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.ccxt_provider import CCXTProvider
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

pytestmark = pytest.mark.contract

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "kucoin"

class _FakeKucoin:
    """Replays saved fixtures as if they were live CCXT responses."""

    def __init__(self) -> None:
        self._ticker = json.loads(
            (FIXTURE_DIR / "fetch_ticker_btc_usdt.json").read_text()
        )
        self._ohlcv = json.loads(
            (FIXTURE_DIR / "fetch_ohlcv_btc_usdt_1h.json").read_text()
        )
        self._ob = json.loads(
            (FIXTURE_DIR / "fetch_order_book_btc_usdt.json").read_text()
        )

    async def load_markets(self) -> dict:
        return {}

    async def fetch_ticker(self, symbol: str) -> dict:
        return self._ticker

    async def fetch_ohlcv(
        self, symbol: str, timeframe: str,
        since: int | None = None, limit: int = 500,
    ) -> list:
        return self._ohlcv

    async def fetch_order_book(self, symbol: str, limit: int = 50) -> dict:
        return self._ob

    async def close(self) -> None:
        return None

@pytest.fixture
def registry() -> SymbolRegistry:
    return SymbolRegistry()

@pytest.fixture
def btc_symbol(registry: SymbolRegistry):
    return registry.get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )

@pytest.fixture
def kucoin_provider(btc_symbol) -> CCXTProvider:
    return CCXTProvider(
        venue_id=VenueId.KUCOIN,
        state=VenueState(VenueId.KUCOIN),
        exchange=_FakeKucoin(),
    )

async def test_full_ticker_path(kucoin_provider: CCXTProvider, btc_symbol) -> None:
    ticker = await kucoin_provider.fetch_ticker(btc_symbol)
    assert ticker.last == Decimal("65000.5")
    assert ticker.quality.source.venue_id == "kucoin"

async def test_full_ohlcv_path(kucoin_provider: CCXTProvider, btc_symbol) -> None:
    series = await kucoin_provider.fetch_ohlcv(
        btc_symbol, Timeframe.H1, limit=5,
    )
    assert len(series.candles) == 5
    assert series.candles[0].open == Decimal("64000.0")
    assert series.candles[-1].close == Decimal("65200.0")

async def test_full_orderbook_path(kucoin_provider: CCXTProvider, btc_symbol) -> None:
    ob = await kucoin_provider.fetch_order_book(btc_symbol, depth=3)
    assert ob.best_bid() is not None
    assert ob.best_ask() is not None
    spread = ob.spread()
    assert spread is not None
    assert spread == Decimal("2.0")  # 65001.5 - 64999.5
```

- [ ] **Step 2: Add `contract` marker to pyproject.toml**

Check existing markers in pyproject.toml (should already include `contract` from M1 setup). If not, edit:

```toml
markers = [
    "unit: unit tests (fast, no I/O)",
    "contract: contract tests against saved fixtures",
    "integration: integration tests (require supabase start)",
    "mcp: MCP server direct-call tests",
    "e2e: end-to-end tests (STDIO roundtrip)",
]
```

Already present from M1. Skip if so.

- [ ] **Step 3: Run**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/contract/test_kucoin_provider_contract.py -v -m contract
```

Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add tests/contract/test_kucoin_provider_contract.py
```

Write to `/tmp/commit-msg.txt`:
```text
test(providers): add KuCoin contract tests using saved fixtures

FakeKucoin replays 3 JSON fixtures; CCXTProvider + CCXTAdapter +
BaseProvider stack is exercised end-to-end offline. Marker @contract
separates from unit (fast mock-free) and integration (live network).
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 10: Full verification + tag v0.0.4

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `docs/superpowers/plans/2026-04-21-cryptozavr-m2.3a-core-providers.md` (this file — already committed at M2.2 finalize or will be committed now if missing)

- [ ] **Step 1: Verify**

```bash
cd /Users/laptop/dev/cryptozavr
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest tests/unit tests/contract -v -m "not integration" --cov=cryptozavr.infrastructure.providers --cov-report=term
```

Expected: all green. Unit + contract tests pass (no integration markers — those require Docker).

- [ ] **Step 2: Update CHANGELOG**

Edit `/Users/laptop/dev/cryptozavr/CHANGELOG.md`. Find:

```markdown
## [Unreleased]

## [0.0.3] - 2026-04-21
```

Replace with:

```markdown
## [Unreleased]

## [0.0.4] - 2026-04-21

### Added — M2.3a Core providers
- `HttpClientRegistry`: per-venue httpx.AsyncClient pool (Singleton via DI).
- `TokenBucket` + `RateLimiterRegistry`: classic token-bucket rate limiter with asyncio.Lock-safe acquire.
- `VenueState`: minimal State context holding current VenueStateKind; `require_operational()` raises on RATE_LIMITED/DOWN. Full transition rules in M2.3b.
- `BaseProvider`: Template Method skeleton (require_operational → ensure_markets → fetch_raw → normalize → translate_exception) for ticker/ohlcv/orderbook/trades pipelines.
- `CCXTAdapter`: pure static functions converting CCXT unified format to Domain (ticker/ohlcv/orderbook).
- `CCXTProvider`: concrete BaseProvider wrapping ccxt.async_support (`for_kucoin` classmethod convenience). Exception translation: CCXT.RateLimitExceeded → RateLimitExceededError; CCXT.NetworkError → ProviderUnavailableError.
- Contract tests: `tests/contract/` with saved KuCoin JSON fixtures (ticker/ohlcv/orderbook) and end-to-end provider test via FakeKucoin replay.
- New deps: ccxt, httpx (m2 group); respx, freezegun (dev group).

### Deferred to M2.3b
- CoinGeckoAdapter + CoinGeckoProvider.
- 4 Decorators: Retry, RateLimit, InMemoryCaching, Logging.
- Full VenueState transition rules (HealthyState/DegradedState/RateLimitedState/DownState behaviours).

## [0.0.3] - 2026-04-21
```

- [ ] **Step 3: Ensure plan file is committed**

```bash
cd /Users/laptop/dev/cryptozavr
git status
```

If `docs/superpowers/plans/2026-04-21-cryptozavr-m2.3a-core-providers.md` is untracked, add it alongside CHANGELOG in the same commit.

- [ ] **Step 4: Commit + tag**

```bash
cd /Users/laptop/dev/cryptozavr
git add CHANGELOG.md
# If plan is untracked:
git add docs/superpowers/plans/2026-04-21-cryptozavr-m2.3a-core-providers.md 2>/dev/null || true
```

Write to `/tmp/commit-msg.txt`:
```bash
docs: finalize CHANGELOG for v0.0.4 (M2.3a Core providers)
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt

git tag -a v0.0.4 -m "M2.3a Core providers complete

BaseProvider Template Method + CCXTProvider + CCXTAdapter +
HttpClientRegistry + RateLimiterRegistry + VenueState minimal.
Contract tests via saved KuCoin fixtures.
Ready for M2.3b (CoinGecko + Decorators + State transitions)."
```

- [ ] **Step 5: Summary**

```bash
cd /Users/laptop/dev/cryptozavr
echo "=== M2.3a complete ==="
git log --oneline v0.0.3..HEAD
git tag -l
```

**No push** — remote still deferred.

---

## Acceptance Criteria for M2.3a

1. ✅ All 10 tasks executed.
2. ✅ Unit tests ≥ 25 new, all pass.
3. ✅ Contract tests (3 tests) pass.
4. ✅ Mypy clean across new providers modules.
5. ✅ Ruff clean.
6. ✅ Provider coverage on adapter + base + http + rate_limiters ≥ 90%.
7. ✅ CCXTProvider works end-to-end via FakeKucoin fixtures (no network).
8. ✅ Tag `v0.0.4` at HEAD.

---

## Handoff to M2.3b

After M2.3a complete, invoke `writing-plans` with:
"M2.3a complete (v0.0.4). Write plan for M2.3b: CoinGeckoAdapter + CoinGeckoProvider (using httpx + HttpClientRegistry) + 4 Decorators (Retry/RateLimit/Caching/Logging) + VenueState full State-pattern transitions (Healthy/Degraded/RateLimited/Down with on_request_succeeded/failed). ~10 tasks, target tag v0.0.5."

---

## Notes

- **Fake exchange vs respx.** CCXT's internal HTTP flow is multi-layered; mocking at HTTPX level is brittle. Injecting a duck-typed fake exchange gives stable, readable tests. respx will be more valuable for CoinGecko in M2.3b (direct httpx calls).
- **BaseProvider doesn't catch ProviderUnavailableError from require_operational.** That error bubbles out directly — callers get clean "venue is down/rate_limited" signals without exception translation interference.
- **Contract fixtures are hand-written, not recorded.** Small synthetic BTC/USDT snapshots keep tests deterministic and independent from real market fluctuations. Larger fixtures will arrive in M2.3c or phase 2 when backtest engine wants real historical windows.
