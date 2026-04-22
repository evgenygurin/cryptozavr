# Position Watcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build real-time position monitoring with event-driven WebSocket streaming so the user can track an active paper-trading position without blocking the MCP session.

**Architecture:** Detached `asyncio.Task` + mutable registry in FastMCP lifespan. `ccxt.pro.kucoin` WebSocket for tick-level updates. Three MCP tools (`watch_position`, `check_watch`, `stop_watch`) polled by the client — no `task=True` or `progressToken` dependency.

**Tech Stack:** Python 3.12, FastMCP v3.2.4+, ccxt 4.5 (with `.pro` async WebSocket), asyncio, Pydantic v2, pytest.

**Spec:** `docs/superpowers/specs/2026-04-22-position-watcher-design.md`

---

## File Structure

### New files

- `src/cryptozavr/domain/watch.py` — frozen dataclasses / enums (`WatchSide`, `WatchStatus`, `EventType`, `WatchEvent`) + mutable `WatchState`.
- `src/cryptozavr/application/services/position_watcher.py` — `EventDetector` (pure), `PositionWatcher` (start/check/stop/loop).
- `src/cryptozavr/infrastructure/providers/kucoin_ws.py` — `KucoinWsProvider` wrapping `ccxt.pro.kucoin`.
- `src/cryptozavr/mcp/tools/watch.py` — three MCP tools.
- `tests/unit/domain/test_watch.py`
- `tests/unit/application/services/test_event_detector.py`
- `tests/unit/application/services/test_position_watcher.py`
- `tests/unit/mcp/tools/test_watch_tools.py`
- `tests/integration/test_watch_kucoin_live.py`

### Modified files

- `src/cryptozavr/domain/exceptions.py` — add `WatchNotFoundError`.
- `src/cryptozavr/mcp/lifespan_state.py` — add `ws_provider`, `watch_registry`, `position_watcher` keys + getters.
- `src/cryptozavr/mcp/bootstrap.py` — init `KucoinWsProvider`, `PositionWatcher`, put in dict; teardown callback.
- `src/cryptozavr/mcp/server.py` — call `register_watch_tools(mcp)`.
- `src/cryptozavr/mcp/dtos.py` — add `WatchIdDTO`, `WatchEventDTO`, `WatchStateDTO`.
- `CHANGELOG.md` — document the feature.

---

## Task 1: Domain types — enums + frozen events

**Files:**
- Create: `src/cryptozavr/domain/watch.py`
- Test: `tests/unit/domain/test_watch.py`

- [ ] **Step 1.1: Write the failing tests**

```python
# tests/unit/domain/test_watch.py
from decimal import Decimal

import pytest

from cryptozavr.domain.watch import (
    EventType,
    WatchEvent,
    WatchSide,
    WatchStatus,
)

class TestWatchEnums:
    def test_side_values(self) -> None:
        assert WatchSide.LONG.value == "long"
        assert WatchSide.SHORT.value == "short"

    def test_status_values(self) -> None:
        assert WatchStatus.RUNNING.value == "running"
        assert WatchStatus.STOP_HIT.value == "stop_hit"
        assert WatchStatus.TAKE_HIT.value == "take_hit"
        assert WatchStatus.TIMEOUT.value == "timeout"
        assert WatchStatus.CANCELLED.value == "cancelled"
        assert WatchStatus.ERROR.value == "error"

    def test_event_type_terminal_flag(self) -> None:
        assert EventType.STOP_HIT.is_terminal
        assert EventType.TAKE_HIT.is_terminal
        assert EventType.TIMEOUT.is_terminal
        assert not EventType.PRICE_APPROACHES_STOP.is_terminal
        assert not EventType.PRICE_APPROACHES_TAKE.is_terminal
        assert not EventType.BREAKEVEN_REACHED.is_terminal

class TestWatchEvent:
    def test_construction(self) -> None:
        event = WatchEvent(
            type=EventType.STOP_HIT,
            ts_ms=1_000_000,
            price=Decimal("79100"),
            details={"reason": "crossed"},
        )
        assert event.type is EventType.STOP_HIT
        assert event.price == Decimal("79100")

    def test_frozen(self) -> None:
        event = WatchEvent(
            type=EventType.STOP_HIT,
            ts_ms=0,
            price=Decimal("0"),
            details={},
        )
        with pytest.raises(Exception):  # noqa: B017 — FrozenInstanceError/AttributeError both acceptable
            event.price = Decimal("1")  # type: ignore[misc]
```

- [ ] **Step 1.2: Verify tests fail**

Run: `uv run pytest tests/unit/domain/test_watch.py -v`
Expected: FAIL — `ModuleNotFoundError: cryptozavr.domain.watch`

- [ ] **Step 1.3: Implement domain types**

```python
# src/cryptozavr/domain/watch.py
"""Watch types: enums, frozen events, and mutable state.

WatchState is mutable (lives in registry and is updated tick-by-tick by
the watch loop). WatchEvent is frozen (append-only history). Enums and
flags are module-level constants.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

class WatchSide(StrEnum):
    LONG = "long"
    SHORT = "short"

class WatchStatus(StrEnum):
    RUNNING = "running"
    STOP_HIT = "stop_hit"
    TAKE_HIT = "take_hit"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    ERROR = "error"

class EventType(StrEnum):
    PRICE_APPROACHES_STOP = "price_approaches_stop"
    PRICE_APPROACHES_TAKE = "price_approaches_take"
    BREAKEVEN_REACHED = "breakeven_reached"
    STOP_HIT = "stop_hit"
    TAKE_HIT = "take_hit"
    TIMEOUT = "timeout"

    @property
    def is_terminal(self) -> bool:
        return self in _TERMINAL_EVENT_TYPES

_TERMINAL_EVENT_TYPES: frozenset[EventType] = frozenset(
    {EventType.STOP_HIT, EventType.TAKE_HIT, EventType.TIMEOUT}
)

@dataclass(frozen=True, slots=True)
class WatchEvent:
    type: EventType
    ts_ms: int
    price: Decimal
    details: dict[str, str] = field(default_factory=dict)
```

- [ ] **Step 1.4: Verify enum + event tests pass**

Run: `uv run pytest tests/unit/domain/test_watch.py -v`
Expected: 3 PASS

- [ ] **Step 1.5: Add WatchState tests**

Append to `tests/unit/domain/test_watch.py`:

```python
from cryptozavr.domain.exceptions import ValidationError
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.domain.watch import WatchState

@pytest.fixture
def btc_symbol():
    reg = SymbolRegistry()
    return reg.get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )

class TestWatchState:
    def test_valid_long(self, btc_symbol) -> None:
        state = WatchState(
            watch_id="abc",
            symbol=btc_symbol,
            side=WatchSide.LONG,
            entry=Decimal("100"),
            stop=Decimal("95"),
            take=Decimal("110"),
            size_quote=None,
            started_at_ms=1_000,
            max_duration_sec=3600,
        )
        assert state.status is WatchStatus.RUNNING
        assert state.events == []

    def test_long_stop_must_be_below_entry(self, btc_symbol) -> None:
        with pytest.raises(ValidationError, match="stop < entry"):
            WatchState(
                watch_id="abc", symbol=btc_symbol, side=WatchSide.LONG,
                entry=Decimal("100"), stop=Decimal("105"), take=Decimal("110"),
                size_quote=None, started_at_ms=0, max_duration_sec=60,
            )

    def test_short_take_must_be_below_entry(self, btc_symbol) -> None:
        with pytest.raises(ValidationError, match="take < entry"):
            WatchState(
                watch_id="abc", symbol=btc_symbol, side=WatchSide.SHORT,
                entry=Decimal("100"), stop=Decimal("110"), take=Decimal("105"),
                size_quote=None, started_at_ms=0, max_duration_sec=60,
            )

    def test_duration_bounds(self, btc_symbol) -> None:
        with pytest.raises(ValidationError, match="max_duration_sec"):
            WatchState(
                watch_id="abc", symbol=btc_symbol, side=WatchSide.LONG,
                entry=Decimal("100"), stop=Decimal("95"), take=Decimal("110"),
                size_quote=None, started_at_ms=0, max_duration_sec=30,  # <60
            )
```

- [ ] **Step 1.6: Run WatchState tests (expected to fail)**

Run: `uv run pytest tests/unit/domain/test_watch.py -v`
Expected: FAIL — `WatchState` not defined.

- [ ] **Step 1.7: Add WatchState to watch.py**

Append to `src/cryptozavr/domain/watch.py`:

```python
import asyncio  # noqa: E402
from typing import TYPE_CHECKING  # noqa: E402

from cryptozavr.domain.exceptions import ValidationError  # noqa: E402

if TYPE_CHECKING:
    from cryptozavr.domain.symbols import Symbol

_MIN_DURATION_SEC = 60
_MAX_DURATION_SEC = 86_400
_EVENT_BUFFER_CAP = 200

@dataclass(slots=True)
class WatchState:
    watch_id: str
    symbol: "Symbol"
    side: WatchSide
    entry: Decimal
    stop: Decimal
    take: Decimal
    size_quote: Decimal | None
    started_at_ms: int
    max_duration_sec: int
    status: WatchStatus = WatchStatus.RUNNING
    current_price: Decimal | None = None
    last_tick_at_ms: int | None = None
    pnl_quote: Decimal | None = None
    pnl_pct: Decimal | None = None
    events: list[WatchEvent] = field(default_factory=list)
    _fired_non_terminal: set[EventType] = field(default_factory=set)
    _task: asyncio.Task[None] | None = None

    def __post_init__(self) -> None:
        if self.entry <= 0 or self.stop <= 0 or self.take <= 0:
            raise ValidationError("entry/stop/take must be positive")
        if self.side is WatchSide.LONG:
            if not (self.stop < self.entry):
                raise ValidationError("long: stop < entry required")
            if not (self.entry < self.take):
                raise ValidationError("long: entry < take required")
        else:
            if not (self.take < self.entry):
                raise ValidationError("short: take < entry required")
            if not (self.entry < self.stop):
                raise ValidationError("short: entry < stop required")
        if not (_MIN_DURATION_SEC <= self.max_duration_sec <= _MAX_DURATION_SEC):
            raise ValidationError(
                f"max_duration_sec must be in [{_MIN_DURATION_SEC}, "
                f"{_MAX_DURATION_SEC}]"
            )

    def append_event(self, event: WatchEvent) -> None:
        self.events.append(event)
        if len(self.events) > _EVENT_BUFFER_CAP:
            # FIFO eviction
            del self.events[: len(self.events) - _EVENT_BUFFER_CAP]
```

- [ ] **Step 1.8: Verify all domain tests pass**

Run: `uv run pytest tests/unit/domain/test_watch.py -v`
Expected: 7 PASS

- [ ] **Step 1.9: Commit**

```bash
git add src/cryptozavr/domain/watch.py tests/unit/domain/test_watch.py
```

Write commit message to `/tmp/commit-msg.txt`:

```bash
feat(domain): add Watch types for position monitoring

Frozen WatchEvent + mutable WatchState with invariants
(long/short price ordering, duration bounds, ring buffer cap).
```

Run: `git commit -F /tmp/commit-msg.txt && rm /tmp/commit-msg.txt`

---

## Task 2: WatchNotFoundError domain exception

**Files:**
- Modify: `src/cryptozavr/domain/exceptions.py`

- [ ] **Step 2.1: Add exception**

Append after `SymbolNotFoundError` in `src/cryptozavr/domain/exceptions.py`:

```python
class WatchNotFoundError(NotFoundError):
    """Raised when a watch_id does not exist in the registry."""

    def __init__(self, watch_id: str) -> None:
        super().__init__(f"Watch not found: {watch_id!r}")
        self.watch_id = watch_id
```

- [ ] **Step 2.2: Quick smoke test**

Run: `uv run python -c "from cryptozavr.domain.exceptions import WatchNotFoundError; e = WatchNotFoundError('abc'); print(e.watch_id, str(e))"`
Expected output: `abc Watch not found: 'abc'`

- [ ] **Step 2.3: Commit**

```bash
git add src/cryptozavr/domain/exceptions.py
```

`/tmp/commit-msg.txt`:

```text
feat(domain): add WatchNotFoundError

Raised when MCP tool receives unknown watch_id.
```

`git commit -F /tmp/commit-msg.txt && rm /tmp/commit-msg.txt`

---

## Task 3: EventDetector — pure function

**Files:**
- Create: `src/cryptozavr/application/services/position_watcher.py`
- Test: `tests/unit/application/services/test_event_detector.py`

- [ ] **Step 3.1: Write parametrised tests**

```python
# tests/unit/application/services/test_event_detector.py
from decimal import Decimal

import pytest

from cryptozavr.application.services.position_watcher import EventDetector
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.domain.watch import (
    EventType,
    WatchSide,
    WatchState,
    WatchStatus,
)

@pytest.fixture
def btc_symbol():
    reg = SymbolRegistry()
    return reg.get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )

def _long_state(symbol, stop=Decimal("95"), take=Decimal("110")) -> WatchState:
    return WatchState(
        watch_id="w", symbol=symbol, side=WatchSide.LONG,
        entry=Decimal("100"), stop=stop, take=take,
        size_quote=None, started_at_ms=1_000, max_duration_sec=3600,
    )

def _short_state(symbol, stop=Decimal("105"), take=Decimal("90")) -> WatchState:
    return WatchState(
        watch_id="w", symbol=symbol, side=WatchSide.SHORT,
        entry=Decimal("100"), stop=stop, take=take,
        size_quote=None, started_at_ms=1_000, max_duration_sec=3600,
    )

class TestTerminalEventsLong:
    def test_stop_hit(self, btc_symbol) -> None:
        state = _long_state(btc_symbol)
        events = EventDetector.detect(state, price=Decimal("95"), now_ms=2_000)
        assert any(e.type is EventType.STOP_HIT for e in events)

    def test_take_hit(self, btc_symbol) -> None:
        state = _long_state(btc_symbol)
        events = EventDetector.detect(state, price=Decimal("110"), now_ms=2_000)
        assert any(e.type is EventType.TAKE_HIT for e in events)

    def test_timeout_when_deadline_passed(self, btc_symbol) -> None:
        state = _long_state(btc_symbol)
        deadline = state.started_at_ms + state.max_duration_sec * 1000
        events = EventDetector.detect(state, price=Decimal("100"), now_ms=deadline + 1)
        assert any(e.type is EventType.TIMEOUT for e in events)

class TestTerminalEventsShort:
    def test_stop_hit_short(self, btc_symbol) -> None:
        state = _short_state(btc_symbol)
        events = EventDetector.detect(state, price=Decimal("105"), now_ms=2_000)
        assert any(e.type is EventType.STOP_HIT for e in events)

    def test_take_hit_short(self, btc_symbol) -> None:
        state = _short_state(btc_symbol)
        events = EventDetector.detect(state, price=Decimal("90"), now_ms=2_000)
        assert any(e.type is EventType.TAKE_HIT for e in events)

class TestApproachEvents:
    def test_price_approaches_stop_long(self, btc_symbol) -> None:
        state = _long_state(btc_symbol, stop=Decimal("95"))
        # within 0.5% above stop
        events = EventDetector.detect(state, price=Decimal("95.4"), now_ms=2_000)
        types = [e.type for e in events]
        assert EventType.PRICE_APPROACHES_STOP in types

    def test_price_approaches_take_long(self, btc_symbol) -> None:
        state = _long_state(btc_symbol, take=Decimal("110"))
        events = EventDetector.detect(state, price=Decimal("109.5"), now_ms=2_000)
        types = [e.type for e in events]
        assert EventType.PRICE_APPROACHES_TAKE in types

    def test_approach_fires_once(self, btc_symbol) -> None:
        state = _long_state(btc_symbol, stop=Decimal("95"))
        first = EventDetector.detect(state, price=Decimal("95.4"), now_ms=2_000)
        state._fired_non_terminal.update(e.type for e in first)
        second = EventDetector.detect(state, price=Decimal("95.4"), now_ms=2_001)
        assert all(e.type is not EventType.PRICE_APPROACHES_STOP for e in second)

class TestBreakeven:
    def test_breakeven_long(self, btc_symbol) -> None:
        # entry=100, stop=95 -> R=5. Price=105 -> pnl=5 = 1R.
        state = _long_state(btc_symbol, stop=Decimal("95"))
        events = EventDetector.detect(state, price=Decimal("105"), now_ms=2_000)
        assert any(e.type is EventType.BREAKEVEN_REACHED for e in events)

    def test_breakeven_short(self, btc_symbol) -> None:
        # entry=100, stop=105 -> R=5. Price=95 -> pnl=5 = 1R.
        state = _short_state(btc_symbol, stop=Decimal("105"))
        events = EventDetector.detect(state, price=Decimal("95"), now_ms=2_000)
        assert any(e.type is EventType.BREAKEVEN_REACHED for e in events)

class TestNoEvent:
    def test_far_from_levels(self, btc_symbol) -> None:
        state = _long_state(btc_symbol)
        events = EventDetector.detect(state, price=Decimal("100.5"), now_ms=2_000)
        assert events == []
```

- [ ] **Step 3.2: Verify tests fail**

Run: `uv run pytest tests/unit/application/services/test_event_detector.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3.3: Implement EventDetector**

```python
# src/cryptozavr/application/services/position_watcher.py
"""Position watcher service: EventDetector (pure) + PositionWatcher (stateful)."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.domain.watch import (
    EventType,
    WatchEvent,
    WatchSide,
    WatchState,
)

_APPROACH_BAND_PCT = Decimal("0.005")  # 0.5%

class EventDetector:
    """Pure detector: (state, price, now_ms) -> list[WatchEvent].

    Terminal events (stop/take/timeout) returned first. Non-terminal
    events deduplicated against state._fired_non_terminal.
    """

    @staticmethod
    def detect(
        state: WatchState, *, price: Decimal, now_ms: int
    ) -> list[WatchEvent]:
        events: list[WatchEvent] = []
        # Terminal first: stop
        if _is_stop_hit(state.side, price, state.stop):
            return [WatchEvent(EventType.STOP_HIT, now_ms, price, {})]
        # Terminal: take
        if _is_take_hit(state.side, price, state.take):
            return [WatchEvent(EventType.TAKE_HIT, now_ms, price, {})]
        # Terminal: timeout
        deadline_ms = state.started_at_ms + state.max_duration_sec * 1000
        if now_ms >= deadline_ms:
            return [WatchEvent(EventType.TIMEOUT, now_ms, price, {})]

        # Non-terminal (fire-once)
        if (
            EventType.PRICE_APPROACHES_STOP not in state._fired_non_terminal
            and _is_near_stop(state.side, price, state.stop)
        ):
            events.append(
                WatchEvent(EventType.PRICE_APPROACHES_STOP, now_ms, price, {})
            )
        if (
            EventType.PRICE_APPROACHES_TAKE not in state._fired_non_terminal
            and _is_near_take(state.side, price, state.take)
        ):
            events.append(
                WatchEvent(EventType.PRICE_APPROACHES_TAKE, now_ms, price, {})
            )
        if (
            EventType.BREAKEVEN_REACHED not in state._fired_non_terminal
            and _is_breakeven(state, price)
        ):
            events.append(
                WatchEvent(EventType.BREAKEVEN_REACHED, now_ms, price, {})
            )
        return events

def _is_stop_hit(side: WatchSide, price: Decimal, stop: Decimal) -> bool:
    if side is WatchSide.LONG:
        return price <= stop
    return price >= stop

def _is_take_hit(side: WatchSide, price: Decimal, take: Decimal) -> bool:
    if side is WatchSide.LONG:
        return price >= take
    return price <= take

def _is_near_stop(side: WatchSide, price: Decimal, stop: Decimal) -> bool:
    band = stop * _APPROACH_BAND_PCT
    if side is WatchSide.LONG:
        return stop < price <= stop + band
    return stop - band <= price < stop

def _is_near_take(side: WatchSide, price: Decimal, take: Decimal) -> bool:
    band = take * _APPROACH_BAND_PCT
    if side is WatchSide.LONG:
        return take - band <= price < take
    return take < price <= take + band

def _is_breakeven(state: WatchState, price: Decimal) -> bool:
    r = (state.entry - state.stop).copy_abs()
    if state.side is WatchSide.LONG:
        return price - state.entry >= r
    return state.entry - price >= r
```

- [ ] **Step 3.4: Verify all detector tests pass**

Run: `uv run pytest tests/unit/application/services/test_event_detector.py -v`
Expected: ~10 PASS

- [ ] **Step 3.5: Commit**

```bash
git add src/cryptozavr/application/services/position_watcher.py tests/unit/application/services/test_event_detector.py
```

`/tmp/commit-msg.txt`:

```bash
feat(application): add EventDetector for position watcher

Pure function detects terminal (stop/take/timeout) and fire-once
events (approach_*/breakeven) for long and short sides.
```

`git commit -F /tmp/commit-msg.txt && rm /tmp/commit-msg.txt`

---

## Task 4: KucoinWsProvider

**Files:**
- Create: `src/cryptozavr/infrastructure/providers/kucoin_ws.py`

- [ ] **Step 4.1: Add ccxt.pro dependency check**

Run: `uv run python -c "import ccxt.pro; print(hasattr(ccxt.pro, 'kucoin'))"`
Expected: `True`. If `False`, stop and install `ccxt[pro]` — not expected given current ccxt 4.5.

- [ ] **Step 4.2: Implement provider (no tests yet — pure infra wrapper, covered by integration test later)**

```python
# src/cryptozavr/infrastructure/providers/kucoin_ws.py
"""Thin async generator wrapper around ccxt.pro.kucoin for WS ticker streams.

ccxt.pro handles reconnects + exponential backoff internally. We
translate ccxt.BadSymbol -> SymbolNotFoundError; everything else
propagates.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

import ccxt.pro as ccxt_pro  # type: ignore[import-untyped]

from cryptozavr.domain.exceptions import (
    ProviderUnavailableError,
    SymbolNotFoundError,
)

_LOG = logging.getLogger(__name__)

class KucoinWsProvider:
    """Shared ccxt.pro.kucoin instance — lazy-init, closed on lifespan exit."""

    def __init__(self) -> None:
        self._exchange: Any | None = None
        self._lock = asyncio.Lock()

    async def _ensure(self) -> Any:
        async with self._lock:
            if self._exchange is None:
                self._exchange = ccxt_pro.kucoin({"newUpdates": True})
        return self._exchange

    async def watch_ticker(
        self, native_symbol: str
    ) -> AsyncIterator[tuple[Decimal, int]]:
        """Yield (last_price, observed_at_ms) until caller stops iterating."""
        exchange = await self._ensure()
        ccxt_symbol = _native_to_ccxt(native_symbol)
        while True:
            try:
                raw = await exchange.watch_ticker(ccxt_symbol)
            except ccxt_pro.BadSymbol as exc:
                raise SymbolNotFoundError(
                    user_input=native_symbol, venue="kucoin"
                ) from exc
            except ccxt_pro.NetworkError as exc:
                _LOG.warning("kucoin WS NetworkError, reconnecting: %s", exc)
                continue
            except Exception as exc:  # noqa: BLE001
                raise ProviderUnavailableError(
                    f"kucoin WS failure: {exc}"
                ) from exc
            last = raw.get("last")
            ts = raw.get("timestamp")
            if last is None or ts is None:
                continue
            yield Decimal(str(last)), int(ts)

    async def close(self) -> None:
        if self._exchange is not None:
            try:
                await self._exchange.close()
            finally:
                self._exchange = None

def _native_to_ccxt(native: str) -> str:
    """KuCoin native ('BTC-USDT') → ccxt canonical ('BTC/USDT')."""
    return native.replace("-", "/", 1)
```

- [ ] **Step 4.3: Lint + type-check**

```bash
uv run ruff check src/cryptozavr/infrastructure/providers/kucoin_ws.py
uv run mypy src/cryptozavr/infrastructure/providers/kucoin_ws.py
```

Expected: clean.

- [ ] **Step 4.4: Commit**

```bash
git add src/cryptozavr/infrastructure/providers/kucoin_ws.py
```

`/tmp/commit-msg.txt`:

```text
feat(infra): add KucoinWsProvider using ccxt.pro

Lazy-init shared ccxt.pro.kucoin, translate BadSymbol -> domain
exception, let ccxt.pro auto-reconnect on NetworkError.
```

`git commit -F /tmp/commit-msg.txt && rm /tmp/commit-msg.txt`

---

## Task 5: PositionWatcher — start/stop/check + loop

**Files:**
- Modify: `src/cryptozavr/application/services/position_watcher.py`
- Test: `tests/unit/application/services/test_position_watcher.py`

- [ ] **Step 5.1: Write tests with FakeWsProvider**

```python
# tests/unit/application/services/test_position_watcher.py
import asyncio
from collections.abc import AsyncIterator
from decimal import Decimal

import pytest

from cryptozavr.application.services.position_watcher import PositionWatcher
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.domain.watch import WatchSide, WatchStatus

@pytest.fixture
def btc_symbol():
    reg = SymbolRegistry()
    return reg.get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )

class FakeWsProvider:
    """Yields a scripted sequence of (price, ts_ms) tuples then blocks."""

    def __init__(self, ticks: list[tuple[Decimal, int]], hold_open: bool = True) -> None:
        self._ticks = ticks
        self._hold_open = hold_open

    async def watch_ticker(self, native_symbol: str) -> AsyncIterator[tuple[Decimal, int]]:
        for tick in self._ticks:
            yield tick
        if self._hold_open:
            await asyncio.Event().wait()  # never returns — emulates live stream

    async def close(self) -> None:  # pragma: no cover
        pass

async def test_start_registers_watch(btc_symbol) -> None:
    ws = FakeWsProvider([(Decimal("100"), 1_000_000)])
    registry: dict = {}
    watcher = PositionWatcher(ws_provider=ws, registry=registry)

    watch_id = await watcher.start(
        symbol=btc_symbol,
        side=WatchSide.LONG,
        entry=Decimal("100"),
        stop=Decimal("95"),
        take=Decimal("110"),
        size_quote=None,
        max_duration_sec=3600,
    )
    assert watch_id in registry
    state = registry[watch_id]
    assert state.status is WatchStatus.RUNNING
    # let one tick process
    await asyncio.sleep(0.05)

async def test_stop_hit_terminates_loop(btc_symbol) -> None:
    ticks = [(Decimal("100"), 1_000), (Decimal("95"), 1_100)]
    ws = FakeWsProvider(ticks, hold_open=False)
    registry: dict = {}
    watcher = PositionWatcher(ws_provider=ws, registry=registry)

    watch_id = await watcher.start(
        symbol=btc_symbol, side=WatchSide.LONG,
        entry=Decimal("100"), stop=Decimal("95"), take=Decimal("110"),
        size_quote=None, max_duration_sec=3600,
    )
    state = registry[watch_id]
    assert state._task is not None
    await asyncio.wait_for(state._task, timeout=1.0)
    assert state.status is WatchStatus.STOP_HIT
    assert any(e.type.value == "stop_hit" for e in state.events)

async def test_stop_cancels_running_task(btc_symbol) -> None:
    ws = FakeWsProvider([(Decimal("100"), 1_000)], hold_open=True)
    registry: dict = {}
    watcher = PositionWatcher(ws_provider=ws, registry=registry)

    watch_id = await watcher.start(
        symbol=btc_symbol, side=WatchSide.LONG,
        entry=Decimal("100"), stop=Decimal("95"), take=Decimal("110"),
        size_quote=None, max_duration_sec=3600,
    )
    await asyncio.sleep(0.05)
    state = await watcher.stop(watch_id)
    assert state.status is WatchStatus.CANCELLED

async def test_check_returns_snapshot(btc_symbol) -> None:
    ws = FakeWsProvider([(Decimal("100"), 1_000)], hold_open=True)
    registry: dict = {}
    watcher = PositionWatcher(ws_provider=ws, registry=registry)

    watch_id = await watcher.start(
        symbol=btc_symbol, side=WatchSide.LONG,
        entry=Decimal("100"), stop=Decimal("95"), take=Decimal("110"),
        size_quote=Decimal("1000"), max_duration_sec=3600,
    )
    await asyncio.sleep(0.05)
    state = watcher.check(watch_id)
    assert state.current_price == Decimal("100")
    await watcher.stop(watch_id)
```

- [ ] **Step 5.2: Verify tests fail**

Run: `uv run pytest tests/unit/application/services/test_position_watcher.py -v`
Expected: FAIL — `PositionWatcher` not defined.

- [ ] **Step 5.3: Implement PositionWatcher**

Append to `src/cryptozavr/application/services/position_watcher.py`:

```python
import asyncio  # noqa: E402
import logging  # noqa: E402
import time  # noqa: E402
import uuid  # noqa: E402
from collections.abc import AsyncIterator  # noqa: E402
from typing import Protocol  # noqa: E402

from cryptozavr.domain.exceptions import WatchNotFoundError  # noqa: E402
from cryptozavr.domain.symbols import Symbol  # noqa: E402
from cryptozavr.domain.watch import (  # noqa: E402
    WatchSide,
    WatchState,
    WatchStatus,
)

_LOG = logging.getLogger(__name__)

class WsProviderProto(Protocol):
    def watch_ticker(
        self, native_symbol: str
    ) -> AsyncIterator[tuple["Decimal", int]]: ...

class PositionWatcher:
    def __init__(
        self,
        *,
        ws_provider: WsProviderProto,
        registry: dict[str, WatchState],
    ) -> None:
        self._ws = ws_provider
        self._registry = registry

    async def start(
        self,
        *,
        symbol: Symbol,
        side: WatchSide,
        entry: "Decimal",
        stop: "Decimal",
        take: "Decimal",
        size_quote: "Decimal | None",
        max_duration_sec: int,
    ) -> str:
        watch_id = uuid.uuid4().hex[:12]
        state = WatchState(
            watch_id=watch_id,
            symbol=symbol,
            side=side,
            entry=entry,
            stop=stop,
            take=take,
            size_quote=size_quote,
            started_at_ms=int(time.time() * 1000),
            max_duration_sec=max_duration_sec,
        )
        self._registry[watch_id] = state
        state._task = asyncio.create_task(self._run(state), name=f"watch-{watch_id}")
        return watch_id

    def check(self, watch_id: str) -> WatchState:
        state = self._registry.get(watch_id)
        if state is None:
            raise WatchNotFoundError(watch_id)
        return state

    async def stop(self, watch_id: str) -> WatchState:
        state = self.check(watch_id)
        task = state._task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if state.status is WatchStatus.RUNNING:
            state.status = WatchStatus.CANCELLED
        return state

    async def _run(self, state: WatchState) -> None:
        try:
            async for price, ts_ms in self._ws.watch_ticker(
                state.symbol.native_symbol
            ):
                state.current_price = price
                state.last_tick_at_ms = ts_ms
                _update_pnl(state, price)

                events = EventDetector.detect(state, price=price, now_ms=ts_ms)
                for event in events:
                    state.append_event(event)
                    if event.type.is_terminal:
                        state.status = WatchStatus(event.type.value)
                        return
                    state._fired_non_terminal.add(event.type)
        except asyncio.CancelledError:
            if state.status is WatchStatus.RUNNING:
                state.status = WatchStatus.CANCELLED
            raise
        except Exception as exc:
            _LOG.exception("watch loop failed: %s", exc)
            state.status = WatchStatus.ERROR

def _update_pnl(state: WatchState, price: "Decimal") -> None:
    from decimal import Decimal as _D
    if state.side is WatchSide.LONG:
        pct = (price - state.entry) / state.entry
    else:
        pct = (state.entry - price) / state.entry
    state.pnl_pct = pct.quantize(_D("0.0001"))
    if state.size_quote is not None:
        state.pnl_quote = (state.size_quote * pct).quantize(_D("0.01"))
```

Also add import line at top of file (after existing imports):

```python
from decimal import Decimal  # add if not already present
```

- [ ] **Step 5.4: Verify all tests pass**

Run: `uv run pytest tests/unit/application/services/test_position_watcher.py tests/unit/application/services/test_event_detector.py -v`
Expected: all PASS.

- [ ] **Step 5.5: Commit**

```bash
git add src/cryptozavr/application/services/position_watcher.py tests/unit/application/services/test_position_watcher.py
```

`/tmp/commit-msg.txt`:

```text
feat(application): add PositionWatcher start/check/stop + loop

Manages WatchState lifecycle via detached asyncio.Task. Translates
EventDetector output into state transitions, handles cancellation
and WS errors gracefully.
```

`git commit -F /tmp/commit-msg.txt && rm /tmp/commit-msg.txt`

---

## Task 6: MCP DTOs

**Files:**
- Modify: `src/cryptozavr/mcp/dtos.py`

- [ ] **Step 6.1: Read existing DTOs to match style**

Run: `uv run python -c "from cryptozavr.mcp.dtos import SymbolDTO; print(SymbolDTO.__doc__)"`

- [ ] **Step 6.2: Add DTOs**

Append to `src/cryptozavr/mcp/dtos.py`:

```python
from cryptozavr.domain.watch import (
    EventType,
    WatchEvent,
    WatchSide,
    WatchState,
    WatchStatus,
)

class WatchIdDTO(BaseModel):
    watch_id: str
    status: WatchStatus
    started_at_ms: int
    expected_end_at_ms: int

    @classmethod
    def from_domain(cls, state: WatchState) -> WatchIdDTO:
        return cls(
            watch_id=state.watch_id,
            status=state.status,
            started_at_ms=state.started_at_ms,
            expected_end_at_ms=(
                state.started_at_ms + state.max_duration_sec * 1000
            ),
        )

class WatchEventDTO(BaseModel):
    type: EventType
    ts_ms: int
    price: Decimal
    details: dict[str, str]

    @classmethod
    def from_domain(cls, event: WatchEvent) -> WatchEventDTO:
        return cls(
            type=event.type,
            ts_ms=event.ts_ms,
            price=event.price,
            details=dict(event.details),
        )

class WatchStateDTO(BaseModel):
    watch_id: str
    symbol: str
    side: WatchSide
    entry: Decimal
    stop: Decimal
    take: Decimal
    size_quote: Decimal | None
    status: WatchStatus
    current_price: Decimal | None
    last_tick_at_ms: int | None
    pnl_quote: Decimal | None
    pnl_pct: Decimal | None
    elapsed_sec: int
    events: list[WatchEventDTO]
    next_event_index: int

    @classmethod
    def from_domain(
        cls, state: WatchState, *, since_event_index: int = 0
    ) -> WatchStateDTO:
        events_slice = state.events[since_event_index:]
        elapsed_ms = (
            (state.last_tick_at_ms or state.started_at_ms)
            - state.started_at_ms
        )
        return cls(
            watch_id=state.watch_id,
            symbol=state.symbol.native_symbol,
            side=state.side,
            entry=state.entry,
            stop=state.stop,
            take=state.take,
            size_quote=state.size_quote,
            status=state.status,
            current_price=state.current_price,
            last_tick_at_ms=state.last_tick_at_ms,
            pnl_quote=state.pnl_quote,
            pnl_pct=state.pnl_pct,
            elapsed_sec=max(0, elapsed_ms // 1000),
            events=[WatchEventDTO.from_domain(e) for e in events_slice],
            next_event_index=len(state.events),
        )
```

If imports `BaseModel`, `Decimal` are not already at module top, ensure they are — check the existing file.

- [ ] **Step 6.3: Smoke test**

Run:
```bash
uv run python -c "from cryptozavr.mcp.dtos import WatchIdDTO, WatchEventDTO, WatchStateDTO; print('OK')"
```
Expected: `OK`.

- [ ] **Step 6.4: Commit**

```bash
git add src/cryptozavr/mcp/dtos.py
```

`/tmp/commit-msg.txt`:

```bash
feat(mcp): add DTOs for position watcher tools

WatchIdDTO, WatchEventDTO, WatchStateDTO with from_domain adapters.
```

`git commit -F /tmp/commit-msg.txt && rm /tmp/commit-msg.txt`

---

## Task 7: Lifespan wiring (keys + getters + bootstrap)

**Files:**
- Modify: `src/cryptozavr/mcp/lifespan_state.py`
- Modify: `src/cryptozavr/mcp/bootstrap.py`

- [ ] **Step 7.1: Add lifespan keys + getter**

In `src/cryptozavr/mcp/lifespan_state.py`:

1. Inside `_LifespanKeys` dataclass, add fields:

```python
    ws_provider: str = "ws_provider"
    position_watcher: str = "position_watcher"
    watch_registry: str = "watch_registry"
```

2. In the `TYPE_CHECKING` block, add:

```python
    from cryptozavr.application.services.position_watcher import PositionWatcher
    from cryptozavr.domain.watch import WatchState
    from cryptozavr.infrastructure.providers.kucoin_ws import KucoinWsProvider
```

3. Append getter:

```python
def get_position_watcher(ctx: Any = _CTX) -> PositionWatcher:
    return cast(
        "PositionWatcher",
        ctx.lifespan_context[LIFESPAN_KEYS.position_watcher],
    )

def get_watch_registry(ctx: Any = _CTX) -> dict[str, WatchState]:
    return cast(
        "dict[str, WatchState]",
        ctx.lifespan_context[LIFESPAN_KEYS.watch_registry],
    )

def get_ws_provider(ctx: Any = _CTX) -> KucoinWsProvider:
    return cast(
        "KucoinWsProvider",
        ctx.lifespan_context[LIFESPAN_KEYS.ws_provider],
    )
```

- [ ] **Step 7.2: Wire into bootstrap**

Open `src/cryptozavr/mcp/bootstrap.py`. Near existing service construction, add:

```python
from cryptozavr.application.services.position_watcher import PositionWatcher
from cryptozavr.infrastructure.providers.kucoin_ws import KucoinWsProvider
```

After the existing `ticker_service = TickerService(...)` block, add:

```python
    ws_provider = KucoinWsProvider()
    watch_registry: dict[str, "WatchState"] = {}
    position_watcher = PositionWatcher(
        ws_provider=ws_provider,
        registry=watch_registry,
    )
```

In the returned dict (the one that becomes `lifespan_context`), add three entries:

```python
        LIFESPAN_KEYS.ws_provider: ws_provider,
        LIFESPAN_KEYS.position_watcher: position_watcher,
        LIFESPAN_KEYS.watch_registry: watch_registry,
```

Add a `TYPE_CHECKING` import for `WatchState`:

```python
if TYPE_CHECKING:
    from cryptozavr.domain.watch import WatchState
```

(or use forward reference string — whichever matches the existing style in the file.)

- [ ] **Step 7.3: Add shutdown cleanup**

Find the teardown / finally block in the lifespan. Add before existing teardown code (or after, depending on order):

```python
    # Cancel any running watches, then close the WS provider.
    for _state in watch_registry.values():
        task = _state._task
        if task is not None and not task.done():
            task.cancel()
    import asyncio as _asyncio  # local to avoid polluting top-level

    await _asyncio.gather(
        *(s._task for s in watch_registry.values() if s._task is not None),
        return_exceptions=True,
    )
    await ws_provider.close()
```

- [ ] **Step 7.4: Smoke test server startup**

Run: `uv run python -c "from cryptozavr.mcp.bootstrap import build_lifespan; print('OK')"`
Expected: no import errors.

Run full unit suite:

```bash
uv run pytest tests/unit -q
```

Expected: all pass.

- [ ] **Step 7.5: Commit**

```bash
git add src/cryptozavr/mcp/lifespan_state.py src/cryptozavr/mcp/bootstrap.py
```

`/tmp/commit-msg.txt`:

```text
feat(mcp): wire KucoinWsProvider + PositionWatcher into lifespan

Adds ws_provider / watch_registry / position_watcher keys plus
graceful shutdown (cancel watches, close WS).
```

`git commit -F /tmp/commit-msg.txt && rm /tmp/commit-msg.txt`

---

## Task 8: MCP tools

**Files:**
- Create: `src/cryptozavr/mcp/tools/watch.py`
- Modify: `src/cryptozavr/mcp/server.py`
- Test: `tests/unit/mcp/tools/test_watch_tools.py`

- [ ] **Step 8.1: Write failing tool tests**

```python
# tests/unit/mcp/tools/test_watch_tools.py
from decimal import Decimal

import pytest
from fastmcp import Client, FastMCP

from cryptozavr.application.services.position_watcher import PositionWatcher
from cryptozavr.application.services.symbol_resolver import SymbolResolver
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.mcp.lifespan_state import LIFESPAN_KEYS
from cryptozavr.mcp.tools.watch import register_watch_tools

class _StubWs:
    async def watch_ticker(self, native: str):
        # one tick at stop price -> stop_hit terminal
        yield Decimal("95"), 2_000

    async def close(self) -> None: ...

@pytest.fixture
def mcp_server():
    reg = SymbolRegistry()
    reg.get(
        __import__("cryptozavr.domain.venues", fromlist=["VenueId", "MarketType"]).VenueId.KUCOIN,
        "BTC", "USDT",
        market_type=__import__("cryptozavr.domain.venues", fromlist=["MarketType"]).MarketType.SPOT,
        native_symbol="BTC-USDT",
    )
    resolver = SymbolResolver(reg)
    registry: dict = {}
    watcher = PositionWatcher(ws_provider=_StubWs(), registry=registry)

    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def lifespan(_server):
        yield {
            LIFESPAN_KEYS.symbol_resolver: resolver,
            LIFESPAN_KEYS.position_watcher: watcher,
            LIFESPAN_KEYS.watch_registry: registry,
        }

    mcp = FastMCP("test", lifespan=lifespan)
    register_watch_tools(mcp)
    return mcp

async def test_watch_position_returns_watch_id(mcp_server) -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "watch_position",
            {
                "venue": "kucoin",
                "symbol": "BTC-USDT",
                "side": "long",
                "entry": "100",
                "stop": "95",
                "take": "110",
                "max_duration_sec": 3600,
            },
        )
        assert result.data["watch_id"]
        assert result.data["status"] == "running"

async def test_check_watch_unknown_id_errors(mcp_server) -> None:
    async with Client(mcp_server) as client:
        with pytest.raises(Exception, match="not found"):
            await client.call_tool("check_watch", {"watch_id": "nope"})

async def test_stop_watch_terminates(mcp_server) -> None:
    async with Client(mcp_server) as client:
        started = await client.call_tool(
            "watch_position",
            {
                "venue": "kucoin", "symbol": "BTC-USDT", "side": "long",
                "entry": "100", "stop": "95", "take": "110",
                "max_duration_sec": 3600,
            },
        )
        watch_id = started.data["watch_id"]
        stopped = await client.call_tool("stop_watch", {"watch_id": watch_id})
        assert stopped.data["status"] in {"cancelled", "stop_hit"}
```

- [ ] **Step 8.2: Verify fails**

Run: `uv run pytest tests/unit/mcp/tools/test_watch_tools.py -v`
Expected: FAIL — module missing.

- [ ] **Step 8.3: Implement the three tools**

```python
# src/cryptozavr/mcp/tools/watch.py
"""MCP tools for position watching: watch_position / check_watch / stop_watch."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.dependencies import Depends
from pydantic import Field

from cryptozavr.application.services.position_watcher import PositionWatcher
from cryptozavr.application.services.symbol_resolver import SymbolResolver
from cryptozavr.domain.exceptions import DomainError
from cryptozavr.domain.watch import WatchSide
from cryptozavr.mcp.dtos import WatchIdDTO, WatchStateDTO
from cryptozavr.mcp.errors import domain_to_tool_error
from cryptozavr.mcp.lifespan_state import (
    get_position_watcher,
    get_symbol_resolver,
)

_RESOLVER: SymbolResolver = Depends(get_symbol_resolver)
_WATCHER: PositionWatcher = Depends(get_position_watcher)

def register_watch_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        name="watch_position",
        description=(
            "Start a background position watch. Returns watch_id immediately. "
            "Polls real-time ticker via WebSocket and emits fire-once events "
            "(price_approaches_stop/take, breakeven_reached) plus terminal "
            "events (stop_hit/take_hit/timeout). Poll via check_watch."
        ),
        tags={"market", "position", "streaming"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def watch_position(  # noqa: PLR0913
        venue: Annotated[str, Field(description="Venue id (only 'kucoin' in v1).")],
        symbol: Annotated[str, Field(description="Native symbol, e.g. BTC-USDT.")],
        side: Annotated[str, Field(description="'long' or 'short'.")],
        entry: Annotated[Decimal, Field(description="Entry price.")],
        stop: Annotated[Decimal, Field(description="Stop price.")],
        take: Annotated[Decimal, Field(description="Take-profit price.")],
        ctx: Context,
        size_quote: Annotated[
            Decimal | None,
            Field(description="Optional USD size (for absolute P&L)."),
        ] = None,
        max_duration_sec: Annotated[
            int, Field(ge=60, le=86_400, description="Max watch duration seconds.")
        ] = 3_600,
        resolver: SymbolResolver = _RESOLVER,
        watcher: PositionWatcher = _WATCHER,
    ) -> WatchIdDTO:
        await ctx.info(f"watch_position {venue}/{symbol} side={side}")
        try:
            resolved = resolver.resolve(user_input=symbol, venue=venue)
            watch_id = await watcher.start(
                symbol=resolved,
                side=WatchSide(side),
                entry=entry,
                stop=stop,
                take=take,
                size_quote=size_quote,
                max_duration_sec=max_duration_sec,
            )
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc
        state = watcher.check(watch_id)
        return WatchIdDTO.from_domain(state)

    @mcp.tool(
        name="check_watch",
        description=(
            "Snapshot of an active watch: current price, P&L, status, and "
            "events since the last check (pass next_event_index from the "
            "previous response as since_event_index)."
        ),
        tags={"market", "position", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def check_watch(
        watch_id: Annotated[str, Field(description="The watch id to inspect.")],
        ctx: Context,
        since_event_index: Annotated[
            int, Field(ge=0, description="Return events[since_event_index:].")
        ] = 0,
        watcher: PositionWatcher = _WATCHER,
    ) -> WatchStateDTO:
        await ctx.info(f"check_watch {watch_id}")
        try:
            state = watcher.check(watch_id)
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc
        return WatchStateDTO.from_domain(state, since_event_index=since_event_index)

    @mcp.tool(
        name="stop_watch",
        description=(
            "Cancel an active watch. Returns the final snapshot."
        ),
        tags={"market", "position"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def stop_watch(
        watch_id: Annotated[str, Field(description="The watch id to cancel.")],
        ctx: Context,
        watcher: PositionWatcher = _WATCHER,
    ) -> WatchStateDTO:
        await ctx.info(f"stop_watch {watch_id}")
        try:
            state = await watcher.stop(watch_id)
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc
        return WatchStateDTO.from_domain(state)
```

- [ ] **Step 8.4: Register in server**

In `src/cryptozavr/mcp/server.py`:

1. Add import near other tool imports:

```python
from cryptozavr.mcp.tools.watch import register_watch_tools
```

2. In the server-building function, where other `register_xxx_tools(mcp)` calls live, add:

```python
    register_watch_tools(mcp)
```

- [ ] **Step 8.5: Run tool tests**

Run: `uv run pytest tests/unit/mcp/tools/test_watch_tools.py -v`
Expected: 3 PASS.

- [ ] **Step 8.6: Run full unit suite**

```bash
uv run pytest tests/unit tests/contract -m "not integration" -q
```

Expected: all pass.

- [ ] **Step 8.7: Commit**

```bash
git add src/cryptozavr/mcp/tools/watch.py src/cryptozavr/mcp/server.py tests/unit/mcp/tools/test_watch_tools.py
```

`/tmp/commit-msg.txt`:

```text
feat(mcp): add watch_position / check_watch / stop_watch tools

Three MCP tools expose PositionWatcher over FastMCP. Standard tools
(no task=True) so any MCP client can poll via check_watch.
```

`git commit -F /tmp/commit-msg.txt && rm /tmp/commit-msg.txt`

---

## Task 9: Integration test against live KuCoin WS

**Files:**
- Create: `tests/integration/test_watch_kucoin_live.py`

- [ ] **Step 9.1: Write integration test**

```python
# tests/integration/test_watch_kucoin_live.py
"""Live WS smoke test. Gated by SKIP_LIVE_TESTS env var."""

from __future__ import annotations

import asyncio
import os
from decimal import Decimal

import pytest

from cryptozavr.application.services.position_watcher import PositionWatcher
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.domain.watch import WatchSide
from cryptozavr.infrastructure.providers.kucoin_ws import KucoinWsProvider

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("SKIP_LIVE_TESTS") == "1",
        reason="live WS skipped",
    ),
]

async def test_live_watch_receives_ticks() -> None:
    ws = KucoinWsProvider()
    try:
        reg = SymbolRegistry()
        btc = reg.get(
            VenueId.KUCOIN, "BTC", "USDT",
            market_type=MarketType.SPOT, native_symbol="BTC-USDT",
        )
        registry: dict = {}
        watcher = PositionWatcher(ws_provider=ws, registry=registry)
        watch_id = await watcher.start(
            symbol=btc,
            side=WatchSide.LONG,
            entry=Decimal("1"),         # absurdly low — never hit stop
            stop=Decimal("0.5"),
            take=Decimal("1_000_000"),  # absurdly high — never hit take
            size_quote=None,
            max_duration_sec=60,
        )

        # give WS time to deliver at least one tick (~5s budget)
        for _ in range(50):
            state = watcher.check(watch_id)
            if state.current_price is not None:
                break
            await asyncio.sleep(0.1)

        state = watcher.check(watch_id)
        assert state.current_price is not None, "no tick received"
        assert state.current_price > Decimal("1")

        final = await watcher.stop(watch_id)
        assert final.status.value == "cancelled"
    finally:
        await ws.close()
```

- [ ] **Step 9.2: Run the live test**

Run: `uv run pytest tests/integration/test_watch_kucoin_live.py -v`
Expected: PASS within ~6s. If it fails with network error, investigate whether KuCoin WS is reachable before assuming the code is wrong.

- [ ] **Step 9.3: Commit**

```bash
git add tests/integration/test_watch_kucoin_live.py
```

`/tmp/commit-msg.txt`:

```bash
test(integration): add live KuCoin WS smoke test for watcher

Verifies KucoinWsProvider + PositionWatcher receive at least one
real tick within 5s and shut down cleanly.
```

`git commit -F /tmp/commit-msg.txt && rm /tmp/commit-msg.txt`

---

## Task 10: Changelog + reload-plugin smoke

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 10.1: Read CHANGELOG format**

Open `CHANGELOG.md`. Identify current "Unreleased" or top-of-file section style.

- [ ] **Step 10.2: Add entry**

Add under `## [Unreleased]` (create the heading if absent):

```markdown
### Added
- Position watcher: `watch_position`, `check_watch`, `stop_watch` MCP
  tools for real-time event-driven monitoring of active paper-trading
  positions via `ccxt.pro.kucoin` WebSocket. Events: stop/take hit,
  timeout (terminal), plus fire-once approach/breakeven signals.
```

- [ ] **Step 10.3: Reload plugin + exit for full Python pickup**

Per `CLAUDE.md`: Python changes require exiting Claude and restarting with `--plugin-dir`. Instruct the human operator:

> "Exit this Claude session and restart with `claude --plugin-dir /Users/laptop/dev/cryptozavr` to pick up the new Python tools. Then run `/cryptozavr:health` — it should still pass, and `watch_position` should appear in the tool list."

- [ ] **Step 10.4: Commit**

```bash
git add CHANGELOG.md
```

`/tmp/commit-msg.txt`:

```text
docs(changelog): note position watcher tools
```

`git commit -F /tmp/commit-msg.txt && rm /tmp/commit-msg.txt`

---

## Task 11: Final verification

- [ ] **Step 11.1: Full test run**

```bash
uv run pytest tests/unit tests/contract -m "not integration" -q
```

Expected: all pass, no regressions.

- [ ] **Step 11.2: Lint + format + types**

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

Expected: all clean.

- [ ] **Step 11.3: Live test (optional, if network allows)**

```bash
uv run pytest tests/integration/test_watch_kucoin_live.py -v
```

Expected: PASS.

- [ ] **Step 11.4: Confirm git history**

```bash
git log --oneline -15
```

Expected: ~10 atomic commits, one per task, all conventional-commit style.
