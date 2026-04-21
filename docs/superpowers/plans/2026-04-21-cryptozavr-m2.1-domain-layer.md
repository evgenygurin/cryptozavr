# cryptozavr — Milestone 2.1: Domain Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Построить чистый Domain layer (L3) из Pydantic value objects, entities, Protocol interfaces, exception hierarchy — без I/O и внешних зависимостей (кроме pydantic). После завершения: `src/cryptozavr/domain/` содержит всю доменную модель MVP, 100+ unit тестов зелёные, coverage ≥ 95% на domain.

**Architecture:** L3 в Layered Onion — immutable value objects + DDD-entities + Protocol interfaces. Применяет паттерны Flyweight (SymbolRegistry), Value Object (Timeframe, Money, Instant), Protocol-based Bridge (MarketDataProvider). Никаких асинхронных операций, никакого I/O. Чистая типизированная модель, тестируется синхронно.

**Tech Stack:** Python 3.12, pydantic v2 (с `frozen=True` для immutability), hypothesis (property-based), polyfactory (factory generators), pytest.

**Milestone position:** M2.1 of 4 sub-milestones of M2 of 4 milestones of MVP.

**Spec reference:** docs/superpowers/specs/2026-04-21-cryptozavr-mvp-design.md раздел 3 (Domain model).
**Prior plans:** docs/superpowers/plans/2026-04-21-cryptozavr-m1-bootstrap.md.

---

## File Structure (создаётся в M2.1)

Все пути относительно `/Users/laptop/dev/cryptozavr/`.

| Path | Responsibility |
|------|---------------|
| `src/cryptozavr/domain/exceptions.py` | `DomainError` base + иерархия (ValidationError, NotFoundError + дети, ProviderError + дети, QualityError + дети) |
| `src/cryptozavr/domain/value_objects.py` | `Timeframe` StrEnum, `Instant` wrapper, `TimeRange`, `Money`, `Percentage`, `PriceSize` |
| `src/cryptozavr/domain/quality.py` | `Staleness`, `Confidence` enums, `Provenance`, `DataQuality` |
| `src/cryptozavr/domain/assets.py` | `AssetCategory` enum, `Asset` entity |
| `src/cryptozavr/domain/venues.py` | `VenueId`, `VenueKind`, `MarketType`, `VenueCapability`, `VenueStateKind` enums; `Venue` entity |
| `src/cryptozavr/domain/symbols.py` | `Symbol` value-like entity + `SymbolRegistry` Flyweight factory |
| `src/cryptozavr/domain/market_data.py` | `Ticker`, `OHLCVCandle`, `OHLCVSeries`, `OrderBookSnapshot`, `TradeTick`, `TradeSide` enum, `MarketSnapshot` |
| `src/cryptozavr/domain/interfaces.py` | `MarketDataProvider` Protocol, `Repository[T]` Protocol, `Clock` Protocol |
| `tests/unit/domain/__init__.py` | Package marker |
| `tests/unit/domain/test_exceptions.py` | Exception hierarchy tests |
| `tests/unit/domain/test_value_objects.py` | Timeframe/Instant/TimeRange/Money/Percentage/PriceSize tests + hypothesis |
| `tests/unit/domain/test_quality.py` | Staleness/Confidence/Provenance/DataQuality tests |
| `tests/unit/domain/test_assets.py` | AssetCategory/Asset tests |
| `tests/unit/domain/test_venues.py` | Venue + enums tests |
| `tests/unit/domain/test_symbols.py` | Symbol + SymbolRegistry Flyweight tests (concurrency-safe) |
| `tests/unit/domain/test_market_data.py` | Ticker/OHLCV/OrderBook/Trades/MarketSnapshot tests |
| `tests/unit/domain/test_interfaces.py` | Protocol structural-subtyping checks |

**Модификации:**
- `pyproject.toml` — добавить `hypothesis>=6.100` и `polyfactory>=2.18` в dev-deps.

---

## Execution Order

Задачи строго упорядочены по зависимостям графа модулей:

```text
exceptions (0 deps)
  → value_objects (uses exceptions)
    → quality (uses value_objects, exceptions)
  → assets (0 deps)
  → venues (0 deps, only enums + simple entity)
    → symbols (uses venues)
      → market_data (uses symbols, value_objects, quality)
        → interfaces (uses market_data, symbols)
```

---

## Tasks

### Task 1: Add hypothesis + polyfactory to dev deps

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Read current pyproject.toml dev-deps**

```bash
cd /Users/laptop/dev/cryptozavr
grep -A 12 "\[project.optional-dependencies\]" pyproject.toml
```

Note current `dev = [...]` list. It currently has: `pytest>=8.3`, `pytest-asyncio>=0.24`, `pytest-cov>=5`, `pytest-xdist>=3.6`, `ruff>=0.6`, `mypy>=1.11`, `pre-commit>=3.8`, `dirty-equals>=0.8`.

- [ ] **Step 2: Add hypothesis and polyfactory**

Use Edit tool to change the `dev = [...]` block in `pyproject.toml`. Find:

```toml
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5",
    "pytest-xdist>=3.6",
    "ruff>=0.6",
    "mypy>=1.11",
    "pre-commit>=3.8",
    "dirty-equals>=0.8",
]
```

Replace with:

```toml
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5",
    "pytest-xdist>=3.6",
    "ruff>=0.6",
    "mypy>=1.11",
    "pre-commit>=3.8",
    "dirty-equals>=0.8",
    "hypothesis>=6.100",
    "polyfactory>=2.18",
]
```

- [ ] **Step 3: Sync deps**

```bash
cd /Users/laptop/dev/cryptozavr
uv sync --all-extras
```

Expected: `+ hypothesis==...`, `+ polyfactory==...` installed.

- [ ] **Step 4: Verify import**

```bash
cd /Users/laptop/dev/cryptozavr
uv run python -c "import hypothesis; import polyfactory; print('ok')"
```

Expected: `ok`.

- [ ] **Step 5: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add pyproject.toml uv.lock
```

Write to `/tmp/commit-msg.txt`:
```bash
chore: add hypothesis + polyfactory to dev deps for M2.1

Domain layer unit tests will use property-based testing (hypothesis)
and typed model factories (polyfactory).
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 2: Create domain test package marker

**Files:**
- Create: `tests/unit/domain/__init__.py`

- [ ] **Step 1: Create directory and empty init**

```bash
cd /Users/laptop/dev/cryptozavr
mkdir -p tests/unit/domain
```

Write empty file to `tests/unit/domain/__init__.py`:
```text
```
(truly empty, 0 bytes)

- [ ] **Step 2: Verify pytest discovers it**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/domain --collect-only 2>&1 | head -5
```

Expected: `no tests ran` — directory exists but empty, no error.

- [ ] **Step 3: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add tests/unit/domain/__init__.py
```

Write to `/tmp/commit-msg.txt`:
```text
test: add tests/unit/domain package marker
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 3: Domain exceptions

**Files:**
- Create: `src/cryptozavr/domain/exceptions.py`
- Create: `tests/unit/domain/test_exceptions.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/domain/test_exceptions.py`:
```python
"""Test domain exception hierarchy."""

from __future__ import annotations

import pytest

from cryptozavr.domain.exceptions import (
    AuthenticationError,
    DomainError,
    IncompleteDataError,
    NotFoundError,
    ProviderError,
    ProviderUnavailableError,
    QualityError,
    RateLimitExceededError,
    StaleDataError,
    SymbolNotFoundError,
    ValidationError,
    VenueNotSupportedError,
)

class TestHierarchy:
    """Every domain exception must derive from DomainError."""

    @pytest.mark.parametrize(
        "exc",
        [
            ValidationError,
            NotFoundError,
            SymbolNotFoundError,
            VenueNotSupportedError,
            ProviderError,
            ProviderUnavailableError,
            RateLimitExceededError,
            AuthenticationError,
            QualityError,
            StaleDataError,
            IncompleteDataError,
        ],
    )
    def test_all_domain_exceptions_descend_from_DomainError(self, exc: type) -> None:
        assert issubclass(exc, DomainError)

    def test_SymbolNotFoundError_is_NotFoundError(self) -> None:
        assert issubclass(SymbolNotFoundError, NotFoundError)

    def test_VenueNotSupportedError_is_NotFoundError(self) -> None:
        assert issubclass(VenueNotSupportedError, NotFoundError)

    def test_ProviderUnavailableError_is_ProviderError(self) -> None:
        assert issubclass(ProviderUnavailableError, ProviderError)

    def test_RateLimitExceededError_is_ProviderError(self) -> None:
        assert issubclass(RateLimitExceededError, ProviderError)

    def test_AuthenticationError_is_ProviderError(self) -> None:
        assert issubclass(AuthenticationError, ProviderError)

    def test_StaleDataError_is_QualityError(self) -> None:
        assert issubclass(StaleDataError, QualityError)

    def test_IncompleteDataError_is_QualityError(self) -> None:
        assert issubclass(IncompleteDataError, QualityError)

class TestInstantiation:
    """All exceptions must accept a message string and carry it."""

    def test_DomainError_accepts_message(self) -> None:
        exc = DomainError("something broke")
        assert str(exc) == "something broke"

    def test_SymbolNotFoundError_has_symbol_and_venue(self) -> None:
        exc = SymbolNotFoundError(user_input="BTC/XYZ", venue="kucoin")
        assert exc.user_input == "BTC/XYZ"
        assert exc.venue == "kucoin"
        assert "BTC/XYZ" in str(exc)
        assert "kucoin" in str(exc)

    def test_VenueNotSupportedError_has_venue(self) -> None:
        exc = VenueNotSupportedError(venue="some-exchange")
        assert exc.venue == "some-exchange"
        assert "some-exchange" in str(exc)
```

- [ ] **Step 2: Run test — must fail**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/domain/test_exceptions.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'cryptozavr.domain.exceptions'`.

- [ ] **Step 3: Implement exceptions**

Write to `src/cryptozavr/domain/exceptions.py`:
```python
"""Domain exception hierarchy for cryptozavr.

All exceptions derive from DomainError. Layer L3 throws these.
Layers L2/L4/L5 translate foreign exceptions (CCXT, Supabase) into these.
"""

from __future__ import annotations

class DomainError(Exception):
    """Root of all domain exceptions. Do not raise directly; use a subclass."""

# -- ValidationError ------------------------------------------------------
class ValidationError(DomainError):
    """Invalid value for a domain constraint (bad input, invariant broken)."""

# -- NotFoundError family -------------------------------------------------
class NotFoundError(DomainError):
    """Requested domain resource does not exist."""

class SymbolNotFoundError(NotFoundError):
    """Requested symbol does not exist on the given venue."""

    def __init__(self, user_input: str, venue: str) -> None:
        self.user_input = user_input
        self.venue = venue
        super().__init__(
            f"symbol {user_input!r} was not found on venue {venue!r}"
        )

class VenueNotSupportedError(NotFoundError):
    """Requested venue is not registered / not supported."""

    def __init__(self, venue: str) -> None:
        self.venue = venue
        super().__init__(f"venue {venue!r} is not supported")

# -- ProviderError family -------------------------------------------------
class ProviderError(DomainError):
    """Provider-layer failures raised as domain exceptions."""

class ProviderUnavailableError(ProviderError):
    """Provider is unreachable (network, outage, rate-limited state)."""

class RateLimitExceededError(ProviderError):
    """Provider rejected the request due to rate limit."""

class AuthenticationError(ProviderError):
    """Provider rejected credentials (reserved for authed endpoints; phase 5+)."""

# -- QualityError family --------------------------------------------------
class QualityError(DomainError):
    """Data quality insufficient for the requested operation."""

class StaleDataError(QualityError):
    """Data is older than the acceptable staleness threshold."""

class IncompleteDataError(QualityError):
    """Partial/truncated response, cannot be used for the requested operation."""
```

- [ ] **Step 4: Run tests — must pass**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/domain/test_exceptions.py -v
```

Expected: 14 passed (11 parametric + 3 instantiation).

- [ ] **Step 5: Run mypy**

```bash
cd /Users/laptop/dev/cryptozavr
uv run mypy src/cryptozavr/domain/exceptions.py
```

Expected: `Success: no issues found in 1 source file`.

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add src/cryptozavr/domain/exceptions.py tests/unit/domain/test_exceptions.py
```

Write to `/tmp/commit-msg.txt`:
```text
feat(domain): add exception hierarchy

DomainError root with 4 families: ValidationError, NotFoundError
(SymbolNotFound/VenueNotSupported), ProviderError
(Unavailable/RateLimit/Auth), QualityError (Stale/Incomplete).
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 4: Value objects — Timeframe + Instant

**Files:**
- Create: `src/cryptozavr/domain/value_objects.py`
- Create: `tests/unit/domain/test_value_objects.py` (starts here; extended in Tasks 5, 6, 7)

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/domain/test_value_objects.py`:
```python
"""Test value objects."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from hypothesis import given, strategies as st

from cryptozavr.domain.exceptions import ValidationError
from cryptozavr.domain.value_objects import Instant, Timeframe

class TestTimeframe:
    def test_all_values_exposed(self) -> None:
        assert Timeframe.M1.value == "1m"
        assert Timeframe.M5.value == "5m"
        assert Timeframe.M15.value == "15m"
        assert Timeframe.M30.value == "30m"
        assert Timeframe.H1.value == "1h"
        assert Timeframe.H4.value == "4h"
        assert Timeframe.D1.value == "1d"
        assert Timeframe.W1.value == "1w"

    @pytest.mark.parametrize(
        ("tf", "expected_ms"),
        [
            (Timeframe.M1, 60_000),
            (Timeframe.M5, 300_000),
            (Timeframe.M15, 900_000),
            (Timeframe.M30, 1_800_000),
            (Timeframe.H1, 3_600_000),
            (Timeframe.H4, 14_400_000),
            (Timeframe.D1, 86_400_000),
            (Timeframe.W1, 604_800_000),
        ],
    )
    def test_to_milliseconds(self, tf: Timeframe, expected_ms: int) -> None:
        assert tf.to_milliseconds() == expected_ms

    def test_to_ccxt_string(self) -> None:
        assert Timeframe.H1.to_ccxt_string() == "1h"
        assert Timeframe.D1.to_ccxt_string() == "1d"

    def test_parse_valid(self) -> None:
        assert Timeframe.parse("1h") == Timeframe.H1
        assert Timeframe.parse("5m") == Timeframe.M5

    def test_parse_invalid_raises_ValidationError(self) -> None:
        with pytest.raises(ValidationError):
            Timeframe.parse("3m")

class TestInstant:
    def test_accepts_utc_datetime(self) -> None:
        dt = datetime(2026, 4, 21, 10, 0, 0, tzinfo=timezone.utc)
        inst = Instant(dt)
        assert inst.to_datetime() == dt

    def test_rejects_naive_datetime(self) -> None:
        naive = datetime(2026, 4, 21, 10, 0, 0)
        with pytest.raises(ValidationError):
            Instant(naive)

    def test_from_ms_roundtrip(self) -> None:
        ms = 1_745_200_800_000  # some ms timestamp
        inst = Instant.from_ms(ms)
        assert inst.to_ms() == ms

    def test_from_iso(self) -> None:
        inst = Instant.from_iso("2026-04-21T10:00:00+00:00")
        assert inst.to_datetime().year == 2026
        assert inst.to_datetime().tzinfo is not None

    def test_isoformat(self) -> None:
        inst = Instant.from_ms(1_745_200_800_000)
        assert "T" in inst.isoformat()
        assert inst.isoformat().endswith("+00:00")

    def test_now_returns_timezone_aware(self) -> None:
        inst = Instant.now()
        assert inst.to_datetime().tzinfo is not None

    def test_equality_and_hash(self) -> None:
        a = Instant.from_ms(1000)
        b = Instant.from_ms(1000)
        c = Instant.from_ms(2000)
        assert a == b
        assert hash(a) == hash(b)
        assert a != c

    def test_ordering(self) -> None:
        earlier = Instant.from_ms(1000)
        later = Instant.from_ms(2000)
        assert earlier < later
        assert later > earlier
        assert earlier <= Instant.from_ms(1000)

    @given(st.integers(min_value=0, max_value=2_000_000_000_000))
    def test_from_ms_to_ms_roundtrip_property(self, ms: int) -> None:
        assert Instant.from_ms(ms).to_ms() == ms
```

- [ ] **Step 2: Run — must fail**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/domain/test_value_objects.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'cryptozavr.domain.value_objects'`.

- [ ] **Step 3: Implement Timeframe and Instant**

Write to `src/cryptozavr/domain/value_objects.py`:
```python
"""Domain value objects: immutable, hashable, zero-I/O."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from functools import total_ordering

from cryptozavr.domain.exceptions import ValidationError

class Timeframe(StrEnum):
    """Candle aggregation interval. Values match CCXT timeframe strings."""

    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"

    _MS_TABLE: dict[str, int] = {}  # type: ignore[misc]  # populated after class body

    def to_milliseconds(self) -> int:
        """Return interval length in milliseconds."""
        return _TIMEFRAME_MS[self]

    def to_ccxt_string(self) -> str:
        """Return the CCXT-compatible timeframe string."""
        return self.value

    @classmethod
    def parse(cls, raw: str) -> Timeframe:
        """Parse a CCXT-style string into a Timeframe.

        Raises:
            ValidationError: if the string is not a supported timeframe.
        """
        try:
            return cls(raw)
        except ValueError as exc:
            raise ValidationError(f"unsupported timeframe: {raw!r}") from exc

_TIMEFRAME_MS: dict[Timeframe, int] = {
    Timeframe.M1: 60_000,
    Timeframe.M5: 5 * 60_000,
    Timeframe.M15: 15 * 60_000,
    Timeframe.M30: 30 * 60_000,
    Timeframe.H1: 60 * 60_000,
    Timeframe.H4: 4 * 60 * 60_000,
    Timeframe.D1: 24 * 60 * 60_000,
    Timeframe.W1: 7 * 24 * 60 * 60_000,
}

@total_ordering
class Instant:
    """UTC-only timestamp wrapper. Rejects naive datetimes at construction."""

    __slots__ = ("_dt",)

    def __init__(self, dt: datetime) -> None:
        if dt.tzinfo is None:
            raise ValidationError(
                "Instant requires a timezone-aware datetime (UTC expected)"
            )
        self._dt = dt.astimezone(timezone.utc)

    @classmethod
    def from_ms(cls, ms: int) -> Instant:
        """Construct from Unix milliseconds (UTC)."""
        return cls(datetime.fromtimestamp(ms / 1000, tz=timezone.utc))

    @classmethod
    def from_iso(cls, iso: str) -> Instant:
        """Parse ISO-8601. Accepts both '+00:00' and 'Z' suffix."""
        return cls(datetime.fromisoformat(iso.replace("Z", "+00:00")))

    @classmethod
    def now(cls) -> Instant:
        return cls(datetime.now(tz=timezone.utc))

    def to_datetime(self) -> datetime:
        return self._dt

    def to_ms(self) -> int:
        return int(self._dt.timestamp() * 1000)

    def isoformat(self) -> str:
        return self._dt.isoformat()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Instant):
            return NotImplemented
        return self._dt == other._dt

    def __lt__(self, other: Instant) -> bool:
        return self._dt < other._dt

    def __hash__(self) -> int:
        return hash(self._dt)

    def __repr__(self) -> str:
        return f"Instant({self._dt.isoformat()!r})"
```

- [ ] **Step 4: Run tests — must pass**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/domain/test_value_objects.py -v
```

Expected: all tests in this file pass (~25 including hypothesis iterations).

- [ ] **Step 5: Run mypy**

```bash
cd /Users/laptop/dev/cryptozavr
uv run mypy src/cryptozavr/domain/value_objects.py
```

Expected: `Success`.

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add src/cryptozavr/domain/value_objects.py tests/unit/domain/test_value_objects.py
```

Write to `/tmp/commit-msg.txt`:
```text
feat(domain): add Timeframe and Instant value objects

Timeframe StrEnum (8 values: M1..W1) with to_milliseconds/to_ccxt_string/parse.
Instant UTC-only datetime wrapper with from_ms/from_iso/now + total_ordering.
Both immutable and hashable.
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 5: Value objects — TimeRange

**Files:**
- Modify: `src/cryptozavr/domain/value_objects.py` (add TimeRange)
- Modify: `tests/unit/domain/test_value_objects.py` (add TestTimeRange class)

- [ ] **Step 1: Add failing tests**

Append to `tests/unit/domain/test_value_objects.py`:
```python
from cryptozavr.domain.value_objects import TimeRange

class TestTimeRange:
    def test_happy_path(self) -> None:
        start = Instant.from_ms(1000)
        end = Instant.from_ms(2000)
        tr = TimeRange(start=start, end=end)
        assert tr.start == start
        assert tr.end == end

    def test_rejects_end_not_after_start(self) -> None:
        same = Instant.from_ms(1000)
        with pytest.raises(ValidationError):
            TimeRange(start=same, end=same)

        with pytest.raises(ValidationError):
            TimeRange(start=Instant.from_ms(2000), end=Instant.from_ms(1000))

    def test_duration_ms(self) -> None:
        tr = TimeRange(start=Instant.from_ms(1000), end=Instant.from_ms(3500))
        assert tr.duration_ms() == 2500

    def test_contains(self) -> None:
        tr = TimeRange(start=Instant.from_ms(1000), end=Instant.from_ms(3000))
        assert tr.contains(Instant.from_ms(1000))  # start inclusive
        assert tr.contains(Instant.from_ms(2000))
        assert not tr.contains(Instant.from_ms(3000))  # end exclusive
        assert not tr.contains(Instant.from_ms(500))
        assert not tr.contains(Instant.from_ms(4000))

    def test_estimate_bars(self) -> None:
        hour_range = TimeRange(
            start=Instant.from_ms(0),
            end=Instant.from_ms(3_600_000 * 10),  # 10 hours
        )
        assert hour_range.estimate_bars(Timeframe.H1) == 10
        assert hour_range.estimate_bars(Timeframe.M30) == 20
```

- [ ] **Step 2: Run — must fail**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/domain/test_value_objects.py::TestTimeRange -v
```

Expected: FAIL with `ImportError: cannot import name 'TimeRange'`.

- [ ] **Step 3: Implement TimeRange**

Append to `src/cryptozavr/domain/value_objects.py`:
```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class TimeRange:
    """Half-open UTC interval [start, end). Invariant: end > start."""

    start: Instant
    end: Instant

    def __post_init__(self) -> None:
        if not (self.end > self.start):
            raise ValidationError(
                f"TimeRange requires end > start, got start={self.start!r} "
                f"end={self.end!r}"
            )

    def duration_ms(self) -> int:
        return self.end.to_ms() - self.start.to_ms()

    def contains(self, moment: Instant) -> bool:
        """True if start <= moment < end."""
        return self.start <= moment < self.end

    def estimate_bars(self, timeframe: Timeframe) -> int:
        """Estimate how many full bars of the given timeframe fit in this range."""
        return self.duration_ms() // timeframe.to_milliseconds()
```

- [ ] **Step 4: Run tests — must pass**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/domain/test_value_objects.py -v
```

Expected: all tests pass (previous + 5 new TimeRange tests).

- [ ] **Step 5: Mypy**

```bash
cd /Users/laptop/dev/cryptozavr
uv run mypy src/cryptozavr/domain/value_objects.py
```

Expected: Success.

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add src/cryptozavr/domain/value_objects.py tests/unit/domain/test_value_objects.py
```

Write to `/tmp/commit-msg.txt`:
```text
feat(domain): add TimeRange value object

Half-open [start, end) interval, invariant end > start.
Methods: duration_ms, contains, estimate_bars(timeframe).
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 6: Value objects — Money, Percentage, PriceSize

**Files:**
- Modify: `src/cryptozavr/domain/value_objects.py`
- Modify: `tests/unit/domain/test_value_objects.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/unit/domain/test_value_objects.py`:
```python
from decimal import Decimal

from cryptozavr.domain.value_objects import Money, Percentage, PriceSize

class TestMoney:
    def test_happy_path(self) -> None:
        m = Money(amount=Decimal("100.50"), currency="USDT")
        assert m.amount == Decimal("100.50")
        assert m.currency == "USDT"

    def test_rejects_lowercase_currency(self) -> None:
        with pytest.raises(ValidationError):
            Money(amount=Decimal("1"), currency="usdt")

    def test_rejects_short_currency(self) -> None:
        with pytest.raises(ValidationError):
            Money(amount=Decimal("1"), currency="US")

    def test_rejects_long_currency(self) -> None:
        with pytest.raises(ValidationError):
            Money(amount=Decimal("1"), currency="USDTTOKEN123")  # 11 chars

    def test_equality_and_hash(self) -> None:
        a = Money(amount=Decimal("1.0"), currency="BTC")
        b = Money(amount=Decimal("1.0"), currency="BTC")
        c = Money(amount=Decimal("1.0"), currency="ETH")
        assert a == b
        assert hash(a) == hash(b)
        assert a != c

class TestPercentage:
    def test_happy_path(self) -> None:
        p = Percentage(value=Decimal("12.5"))
        assert p.value == Decimal("12.5")

    def test_as_fraction(self) -> None:
        assert Percentage(value=Decimal("50")).as_fraction() == Decimal("0.5")
        assert Percentage(value=Decimal("100")).as_fraction() == Decimal("1")

    def test_as_bps(self) -> None:
        assert Percentage(value=Decimal("1")).as_bps() == Decimal("100")
        assert Percentage(value=Decimal("0.01")).as_bps() == Decimal("1")

class TestPriceSize:
    def test_happy_path(self) -> None:
        ps = PriceSize(price=Decimal("60000.50"), size=Decimal("0.125"))
        assert ps.price == Decimal("60000.50")
        assert ps.size == Decimal("0.125")

    def test_rejects_negative_price(self) -> None:
        with pytest.raises(ValidationError):
            PriceSize(price=Decimal("-1"), size=Decimal("1"))

    def test_rejects_non_positive_size(self) -> None:
        with pytest.raises(ValidationError):
            PriceSize(price=Decimal("1"), size=Decimal("0"))
        with pytest.raises(ValidationError):
            PriceSize(price=Decimal("1"), size=Decimal("-0.1"))
```

- [ ] **Step 2: Run — must fail**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/domain/test_value_objects.py -v
```

Expected: FAIL with ImportError for Money/Percentage/PriceSize.

- [ ] **Step 3: Implement Money, Percentage, PriceSize**

Append to `src/cryptozavr/domain/value_objects.py`:
```python
from decimal import Decimal

@dataclass(frozen=True, slots=True)
class Money:
    """Monetary amount in a named currency. Never floats."""

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if not (3 <= len(self.currency) <= 10):
            raise ValidationError(
                f"currency must be 3..10 characters, got {self.currency!r}"
            )
        if not self.currency.isupper() or not self.currency.isalnum():
            raise ValidationError(
                f"currency must be uppercase alphanumeric, got {self.currency!r}"
            )

@dataclass(frozen=True, slots=True)
class Percentage:
    """Percentage value (0..100 range not enforced — can be negative for deltas)."""

    value: Decimal

    def as_fraction(self) -> Decimal:
        """Convert to fraction: 50% -> 0.5."""
        return self.value / Decimal(100)

    def as_bps(self) -> Decimal:
        """Convert to basis points: 1% -> 100 bps."""
        return self.value * Decimal(100)

@dataclass(frozen=True, slots=True)
class PriceSize:
    """Price-size pair used in order book levels. price >= 0, size > 0."""

    price: Decimal
    size: Decimal

    def __post_init__(self) -> None:
        if self.price < 0:
            raise ValidationError(
                f"PriceSize.price must be >= 0, got {self.price}"
            )
        if self.size <= 0:
            raise ValidationError(
                f"PriceSize.size must be > 0, got {self.size}"
            )
```

- [ ] **Step 4: Run tests — must pass**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/domain/test_value_objects.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Mypy**

```bash
cd /Users/laptop/dev/cryptozavr
uv run mypy src/cryptozavr/domain/value_objects.py
```

Expected: Success.

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add src/cryptozavr/domain/value_objects.py tests/unit/domain/test_value_objects.py
```

Write to `/tmp/commit-msg.txt`:
```bash
feat(domain): add Money, Percentage, PriceSize value objects

Money: Decimal amount + validated uppercase 3..10-char currency.
Percentage: Decimal with as_fraction/as_bps conversions.
PriceSize: price >= 0, size > 0 — for order-book levels and trade ticks.
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 7: Quality types (Staleness, Confidence, Provenance, DataQuality)

**Files:**
- Create: `src/cryptozavr/domain/quality.py`
- Create: `tests/unit/domain/test_quality.py`

- [ ] **Step 1: Write failing tests**

Write to `tests/unit/domain/test_quality.py`:
```python
"""Test quality / provenance value objects."""

from __future__ import annotations

import pytest

from cryptozavr.domain.quality import (
    Confidence,
    DataQuality,
    Provenance,
    Staleness,
)
from cryptozavr.domain.value_objects import Instant

class TestStaleness:
    def test_ordering(self) -> None:
        """FRESH < RECENT < STALE < EXPIRED (by severity)."""
        assert Staleness.FRESH < Staleness.RECENT
        assert Staleness.RECENT < Staleness.STALE
        assert Staleness.STALE < Staleness.EXPIRED

    def test_values(self) -> None:
        assert Staleness.FRESH.value == "fresh"
        assert Staleness.EXPIRED.value == "expired"

class TestConfidence:
    def test_values(self) -> None:
        assert Confidence.HIGH.value == "high"
        assert Confidence.UNKNOWN.value == "unknown"

class TestProvenance:
    def test_happy_path(self) -> None:
        p = Provenance(venue_id="kucoin", endpoint="fetch_ticker")
        assert p.venue_id == "kucoin"
        assert p.endpoint == "fetch_ticker"

    def test_str_representation(self) -> None:
        p = Provenance(venue_id="kucoin", endpoint="fetch_ohlcv")
        assert str(p) == "kucoin:fetch_ohlcv"

class TestDataQuality:
    def test_happy_path(self) -> None:
        fetched = Instant.now()
        q = DataQuality(
            source=Provenance(venue_id="kucoin", endpoint="fetch_ticker"),
            fetched_at=fetched,
            staleness=Staleness.FRESH,
            confidence=Confidence.HIGH,
            cache_hit=False,
        )
        assert q.staleness == Staleness.FRESH
        assert q.confidence == Confidence.HIGH
        assert q.cache_hit is False
        assert q.fetched_at == fetched

    def test_immutable(self) -> None:
        q = DataQuality(
            source=Provenance(venue_id="kucoin", endpoint="e"),
            fetched_at=Instant.now(),
            staleness=Staleness.FRESH,
            confidence=Confidence.HIGH,
            cache_hit=False,
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            q.cache_hit = True  # type: ignore[misc]
```

- [ ] **Step 2: Run — must fail**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/domain/test_quality.py -v
```

Expected: FAIL (module not found).

- [ ] **Step 3: Implement quality.py**

`Staleness` is a `StrEnum` (so `.value == "fresh"` etc.) with ordering provided via an external table + `@total_ordering`. This keeps the API string-like while still supporting `<`/`>` severity comparisons.

Write to `src/cryptozavr/domain/quality.py`:
```python
"""Data-quality metadata: provenance, staleness, confidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import total_ordering

from cryptozavr.domain.value_objects import Instant

@total_ordering
class Staleness(StrEnum):
    """Severity-ordered freshness buckets.

    FRESH < RECENT < STALE < EXPIRED (increasing severity).
    Stored as string values ("fresh"/"recent"/...) for JSON-friendliness;
    ordered via `_STALENESS_ORDER` table + `@total_ordering`.
    """

    FRESH = "fresh"
    RECENT = "recent"
    STALE = "stale"
    EXPIRED = "expired"

    def _severity(self) -> int:
        return _STALENESS_ORDER[self]

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Staleness):
            return NotImplemented
        return self._severity() < other._severity()

_STALENESS_ORDER: dict[Staleness, int] = {
    Staleness.FRESH: 0,
    Staleness.RECENT: 1,
    Staleness.STALE: 2,
    Staleness.EXPIRED: 3,
}

class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"

@dataclass(frozen=True, slots=True)
class Provenance:
    """Identifies the source of a data point: venue + endpoint."""

    venue_id: str
    endpoint: str

    def __str__(self) -> str:
        return f"{self.venue_id}:{self.endpoint}"

@dataclass(frozen=True, slots=True)
class DataQuality:
    """Envelope attached to every domain response from providers/gateway."""

    source: Provenance
    fetched_at: Instant
    staleness: Staleness
    confidence: Confidence
    cache_hit: bool
```

- [ ] **Step 4: Run tests — must pass**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/domain/test_quality.py -v
```

Expected: all 8 tests pass.

- [ ] **Step 5: Mypy**

```bash
cd /Users/laptop/dev/cryptozavr
uv run mypy src/cryptozavr/domain/quality.py
```

Expected: Success.

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add src/cryptozavr/domain/quality.py tests/unit/domain/test_quality.py
```

Write to `/tmp/commit-msg.txt`:
```text
feat(domain): add quality/provenance value objects

Staleness (ordered FRESH<RECENT<STALE<EXPIRED), Confidence enum,
Provenance (venue_id:endpoint), DataQuality envelope (source, fetched_at,
staleness, confidence, cache_hit).
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 8: Assets

**Files:**
- Create: `src/cryptozavr/domain/assets.py`
- Create: `tests/unit/domain/test_assets.py`

- [ ] **Step 1: Failing tests**

Write to `tests/unit/domain/test_assets.py`:
```python
"""Test Asset + AssetCategory."""

from __future__ import annotations

import pytest

from cryptozavr.domain.assets import Asset, AssetCategory
from cryptozavr.domain.exceptions import ValidationError

class TestAssetCategory:
    def test_values(self) -> None:
        assert AssetCategory.LAYER_1.value == "layer_1"
        assert AssetCategory.DEFI.value == "defi"
        assert AssetCategory.MEME.value == "meme"
        assert AssetCategory.STABLECOIN.value == "stablecoin"

class TestAsset:
    def test_happy_path(self) -> None:
        a = Asset(code="BTC", name="Bitcoin", category=AssetCategory.LAYER_1)
        assert a.code == "BTC"
        assert a.name == "Bitcoin"
        assert a.category == AssetCategory.LAYER_1

    def test_minimal(self) -> None:
        a = Asset(code="BTC")
        assert a.code == "BTC"
        assert a.name is None
        assert a.category is None
        assert a.coingecko_id is None
        assert a.market_cap_rank is None

    def test_code_uppercased(self) -> None:
        a = Asset(code="BTC")
        assert a.code == "BTC"

    def test_rejects_lowercase_code(self) -> None:
        with pytest.raises(ValidationError):
            Asset(code="btc")

    def test_rejects_empty_code(self) -> None:
        with pytest.raises(ValidationError):
            Asset(code="")

    def test_equality_by_code(self) -> None:
        a = Asset(code="BTC", name="Bitcoin")
        b = Asset(code="BTC", name=None)
        # Asset hashing by code only — two Assets with same code are equal.
        assert a == b
        assert hash(a) == hash(b)
```

- [ ] **Step 2: Run — must fail**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/domain/test_assets.py -v
```

Expected: FAIL (module not found).

- [ ] **Step 3: Implement assets.py**

Write to `src/cryptozavr/domain/assets.py`:
```python
"""Asset entity: BTC, ETH, USDT, ... with optional metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from cryptozavr.domain.exceptions import ValidationError

class AssetCategory(StrEnum):
    LAYER_1 = "layer_1"
    LAYER_2 = "layer_2"
    DEFI = "defi"
    MEME = "meme"
    STABLECOIN = "stablecoin"
    NFT = "nft"
    GAMING = "gaming"
    AI = "ai"
    OTHER = "other"

@dataclass(frozen=True, slots=True, eq=False)
class Asset:
    """Crypto asset. Equality and hash based on `code` only.

    Two Assets with the same code are considered equal even if metadata differs.
    Metadata is enriched over time; identity is the code.
    """

    code: str
    name: str | None = None
    category: AssetCategory | None = None
    market_cap_rank: int | None = None
    coingecko_id: str | None = None
    categories: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.code:
            raise ValidationError("Asset.code must not be empty")
        if not self.code.isupper() or not self.code.replace("_", "").isalnum():
            raise ValidationError(
                f"Asset.code must be uppercase alphanumeric (got {self.code!r})"
            )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Asset):
            return NotImplemented
        return self.code == other.code

    def __hash__(self) -> int:
        return hash(self.code)
```

- [ ] **Step 4: Run tests — must pass**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/domain/test_assets.py -v
```

Expected: all 7 tests pass.

- [ ] **Step 5: Mypy**

```bash
cd /Users/laptop/dev/cryptozavr
uv run mypy src/cryptozavr/domain/assets.py
```

Expected: Success.

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add src/cryptozavr/domain/assets.py tests/unit/domain/test_assets.py
```

Write to `/tmp/commit-msg.txt`:
```text
feat(domain): add Asset + AssetCategory

Asset identified by uppercase alphanumeric code; metadata optional.
Equality/hash based on code only (metadata enriched over time).
AssetCategory enum: LAYER_1, LAYER_2, DEFI, MEME, STABLECOIN, NFT, GAMING, AI, OTHER.
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 9: Venues

**Files:**
- Create: `src/cryptozavr/domain/venues.py`
- Create: `tests/unit/domain/test_venues.py`

- [ ] **Step 1: Failing tests**

Write to `tests/unit/domain/test_venues.py`:
```python
"""Test Venue and its enums."""

from __future__ import annotations

import pytest

from cryptozavr.domain.venues import (
    MarketType,
    Venue,
    VenueCapability,
    VenueId,
    VenueKind,
    VenueStateKind,
)

class TestVenueId:
    def test_values(self) -> None:
        assert VenueId.KUCOIN.value == "kucoin"
        assert VenueId.COINGECKO.value == "coingecko"

class TestVenueKind:
    def test_values(self) -> None:
        assert VenueKind.EXCHANGE_CEX.value == "exchange_cex"
        assert VenueKind.AGGREGATOR.value == "aggregator"
        assert VenueKind.EXCHANGE_DEX.value == "exchange_dex"

class TestMarketType:
    def test_values(self) -> None:
        assert MarketType.SPOT.value == "spot"
        assert MarketType.LINEAR_PERP.value == "linear_perp"
        assert MarketType.INVERSE_PERP.value == "inverse_perp"

class TestVenueCapability:
    def test_values_include_all_mvp_caps(self) -> None:
        expected = {
            "spot_ohlcv",
            "spot_orderbook",
            "spot_trades",
            "spot_ticker",
            "futures_ohlcv",
            "funding_rate",
            "open_interest",
            "market_cap_rank",
            "category_data",
        }
        values = {c.value for c in VenueCapability}
        assert expected.issubset(values)

class TestVenueStateKind:
    def test_values(self) -> None:
        assert VenueStateKind.HEALTHY.value == "healthy"
        assert VenueStateKind.DEGRADED.value == "degraded"
        assert VenueStateKind.RATE_LIMITED.value == "rate_limited"
        assert VenueStateKind.DOWN.value == "down"

class TestVenue:
    def test_happy_path(self) -> None:
        v = Venue(
            id=VenueId.KUCOIN,
            kind=VenueKind.EXCHANGE_CEX,
            capabilities=frozenset(
                {VenueCapability.SPOT_OHLCV, VenueCapability.SPOT_TICKER}
            ),
            state=VenueStateKind.HEALTHY,
        )
        assert v.id == VenueId.KUCOIN
        assert VenueCapability.SPOT_OHLCV in v.capabilities
        assert v.state == VenueStateKind.HEALTHY

    def test_equality_by_id(self) -> None:
        a = Venue(
            id=VenueId.KUCOIN,
            kind=VenueKind.EXCHANGE_CEX,
            capabilities=frozenset({VenueCapability.SPOT_TICKER}),
            state=VenueStateKind.HEALTHY,
        )
        b = Venue(
            id=VenueId.KUCOIN,
            kind=VenueKind.EXCHANGE_CEX,
            capabilities=frozenset({VenueCapability.SPOT_OHLCV}),  # different caps
            state=VenueStateKind.DEGRADED,  # different state
        )
        assert a == b  # identity is id
        assert hash(a) == hash(b)
```

- [ ] **Step 2: Run — must fail**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/domain/test_venues.py -v
```

Expected: FAIL (module not found).

- [ ] **Step 3: Implement venues.py**

Write to `src/cryptozavr/domain/venues.py`:
```python
"""Venue entity: represents an exchange or market-data aggregator."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

class VenueId(StrEnum):
    """Stable venue identifier. Used as natural key across the system."""

    KUCOIN = "kucoin"
    COINGECKO = "coingecko"

class VenueKind(StrEnum):
    """High-level classification of the data source."""

    EXCHANGE_CEX = "exchange_cex"
    AGGREGATOR = "aggregator"
    EXCHANGE_DEX = "exchange_dex"

class MarketType(StrEnum):
    """Instrument market type."""

    SPOT = "spot"
    LINEAR_PERP = "linear_perp"
    INVERSE_PERP = "inverse_perp"

class VenueCapability(StrEnum):
    """Capabilities a venue exposes. Bitmask-like frozenset on Venue."""

    SPOT_OHLCV = "spot_ohlcv"
    SPOT_ORDERBOOK = "spot_orderbook"
    SPOT_TRADES = "spot_trades"
    SPOT_TICKER = "spot_ticker"
    FUTURES_OHLCV = "futures_ohlcv"
    FUNDING_RATE = "funding_rate"
    OPEN_INTEREST = "open_interest"
    MARKET_CAP_RANK = "market_cap_rank"
    CATEGORY_DATA = "category_data"

class VenueStateKind(StrEnum):
    """Operational state of a venue (runtime, updated by L2)."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    RATE_LIMITED = "rate_limited"
    DOWN = "down"

@dataclass(frozen=True, slots=True, eq=False)
class Venue:
    """Identity = `id`. Equality and hashing ignore dynamic state/capabilities."""

    id: VenueId
    kind: VenueKind
    capabilities: frozenset[VenueCapability]
    state: VenueStateKind = VenueStateKind.HEALTHY

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Venue):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
```

- [ ] **Step 4: Run tests — must pass**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/domain/test_venues.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Mypy**

```bash
cd /Users/laptop/dev/cryptozavr
uv run mypy src/cryptozavr/domain/venues.py
```

Expected: Success.

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add src/cryptozavr/domain/venues.py tests/unit/domain/test_venues.py
```

Write to `/tmp/commit-msg.txt`:
```text
feat(domain): add Venue entity + 5 supporting enums

VenueId (KUCOIN/COINGECKO), VenueKind (CEX/AGGREGATOR/DEX),
MarketType (SPOT/LINEAR_PERP/INVERSE_PERP), VenueCapability (9 caps),
VenueStateKind (HEALTHY/DEGRADED/RATE_LIMITED/DOWN). Venue identity = id.
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 10: Symbols + SymbolRegistry Flyweight

**Files:**
- Create: `src/cryptozavr/domain/symbols.py`
- Create: `tests/unit/domain/test_symbols.py`

- [ ] **Step 1: Failing tests**

Write to `tests/unit/domain/test_symbols.py`:
```python
"""Test Symbol + SymbolRegistry Flyweight."""

from __future__ import annotations

import asyncio

import pytest

from cryptozavr.domain.exceptions import ValidationError
from cryptozavr.domain.symbols import Symbol, SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId

class TestSymbol:
    def test_happy_path(self) -> None:
        s = Symbol(
            venue=VenueId.KUCOIN,
            base="BTC",
            quote="USDT",
            market_type=MarketType.SPOT,
            native_symbol="BTC-USDT",
        )
        assert s.base == "BTC"
        assert s.quote == "USDT"
        assert s.venue == VenueId.KUCOIN

    def test_rejects_lowercase_base(self) -> None:
        with pytest.raises(ValidationError):
            Symbol(
                venue=VenueId.KUCOIN,
                base="btc",
                quote="USDT",
                market_type=MarketType.SPOT,
                native_symbol="BTC-USDT",
            )

    def test_equality_by_tuple(self) -> None:
        a = Symbol(
            venue=VenueId.KUCOIN, base="BTC", quote="USDT",
            market_type=MarketType.SPOT, native_symbol="BTC-USDT",
        )
        b = Symbol(
            venue=VenueId.KUCOIN, base="BTC", quote="USDT",
            market_type=MarketType.SPOT, native_symbol="BTC/USDT",  # different native
        )
        assert a == b
        assert hash(a) == hash(b)

class TestSymbolRegistry:
    def test_get_returns_shared_instance(self) -> None:
        registry = SymbolRegistry()
        a = registry.get(
            VenueId.KUCOIN, "BTC", "USDT",
            market_type=MarketType.SPOT, native_symbol="BTC-USDT",
        )
        b = registry.get(
            VenueId.KUCOIN, "BTC", "USDT",
            market_type=MarketType.SPOT, native_symbol="BTC-USDT",
        )
        assert a is b  # identity — Flyweight

    def test_different_venue_produces_different_instance(self) -> None:
        registry = SymbolRegistry()
        a = registry.get(
            VenueId.KUCOIN, "BTC", "USDT",
            market_type=MarketType.SPOT, native_symbol="BTC-USDT",
        )
        b = registry.get(
            VenueId.COINGECKO, "BTC", "USDT",
            market_type=MarketType.SPOT, native_symbol="bitcoin",
        )
        assert a is not b

    def test_find_returns_registered(self) -> None:
        registry = SymbolRegistry()
        s = registry.get(
            VenueId.KUCOIN, "BTC", "USDT",
            market_type=MarketType.SPOT, native_symbol="BTC-USDT",
        )
        assert registry.find(VenueId.KUCOIN, "BTC-USDT") is s
        assert registry.find(VenueId.KUCOIN, "MISSING") is None

    def test_find_by_base(self) -> None:
        registry = SymbolRegistry()
        s = registry.get(
            VenueId.KUCOIN, "ETH", "USDT",
            market_type=MarketType.SPOT, native_symbol="ETH-USDT",
        )
        assert registry.find_by_base(VenueId.KUCOIN, "ETH", quote="USDT") is s
        assert registry.find_by_base(VenueId.KUCOIN, "ETH", quote="BTC") is None

    @pytest.mark.asyncio
    async def test_concurrent_get_yields_same_instance(self) -> None:
        """100 concurrent get() calls must all return the same instance."""
        registry = SymbolRegistry()

        async def fetch() -> Symbol:
            return registry.get(
                VenueId.KUCOIN, "BTC", "USDT",
                market_type=MarketType.SPOT, native_symbol="BTC-USDT",
            )

        results = await asyncio.gather(*(fetch() for _ in range(100)))
        first = results[0]
        assert all(s is first for s in results)
```

- [ ] **Step 2: Run — must fail**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/domain/test_symbols.py -v
```

Expected: FAIL (module not found).

- [ ] **Step 3: Implement symbols.py**

Write to `src/cryptozavr/domain/symbols.py`:
```python
"""Symbol entity + SymbolRegistry Flyweight factory.

Symbol identity = (venue, base, quote, market_type) tuple.
SymbolRegistry caches instances process-wide; `get()` returns the SAME object
for identical identity — canonical Flyweight pattern.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from cryptozavr.domain.exceptions import ValidationError
from cryptozavr.domain.venues import MarketType, VenueId

@dataclass(frozen=True, slots=True, eq=False)
class Symbol:
    """Instrument identity: (venue, base, quote, market_type).

    `native_symbol` is the venue-specific wire format (e.g. 'BTC-USDT' for KuCoin).
    It's metadata, not identity — two Symbols with the same identity tuple
    but different native_symbol strings compare equal.
    """

    venue: VenueId
    base: str
    quote: str
    market_type: MarketType
    native_symbol: str

    def __post_init__(self) -> None:
        for attr in ("base", "quote"):
            val: str = getattr(self, attr)
            if not val:
                raise ValidationError(f"Symbol.{attr} must not be empty")
            if not val.isupper() or not val.replace("_", "").isalnum():
                raise ValidationError(
                    f"Symbol.{attr} must be uppercase alphanumeric (got {val!r})"
                )

    def _identity(self) -> tuple[VenueId, str, str, MarketType]:
        return (self.venue, self.base, self.quote, self.market_type)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Symbol):
            return NotImplemented
        return self._identity() == other._identity()

    def __hash__(self) -> int:
        return hash(self._identity())

class SymbolRegistry:
    """Flyweight factory for Symbol instances.

    Thread-safe: the internal dict is guarded by a lock for concurrent access.
    Process-wide singletons are expected in production (one registry per DI scope);
    for tests, each test can use a fresh SymbolRegistry.
    """

    def __init__(self) -> None:
        self._store: dict[tuple[VenueId, str, str, MarketType], Symbol] = {}
        self._lock = threading.Lock()

    def get(
        self,
        venue: VenueId,
        base: str,
        quote: str,
        *,
        market_type: MarketType = MarketType.SPOT,
        native_symbol: str,
    ) -> Symbol:
        """Return cached Symbol with this identity, or create and cache one."""
        key = (venue, base, quote, market_type)
        with self._lock:
            existing = self._store.get(key)
            if existing is not None:
                return existing
            new_symbol = Symbol(
                venue=venue, base=base, quote=quote,
                market_type=market_type, native_symbol=native_symbol,
            )
            self._store[key] = new_symbol
            return new_symbol

    def find(self, venue: VenueId, native_symbol: str) -> Symbol | None:
        """Look up a previously-registered Symbol by its native_symbol on a venue."""
        with self._lock:
            for sym in self._store.values():
                if sym.venue == venue and sym.native_symbol == native_symbol:
                    return sym
        return None

    def find_by_base(
        self, venue: VenueId, base: str, *, quote: str,
        market_type: MarketType = MarketType.SPOT,
    ) -> Symbol | None:
        """Find Symbol by (venue, base, quote, market_type) without native_symbol knowledge."""
        key = (venue, base, quote, market_type)
        with self._lock:
            return self._store.get(key)
```

- [ ] **Step 4: Run tests — must pass**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/domain/test_symbols.py -v
```

Expected: all 7 tests pass, including the async concurrent test.

- [ ] **Step 5: Mypy**

```bash
cd /Users/laptop/dev/cryptozavr
uv run mypy src/cryptozavr/domain/symbols.py
```

Expected: Success.

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add src/cryptozavr/domain/symbols.py tests/unit/domain/test_symbols.py
```

Write to `/tmp/commit-msg.txt`:
```text
feat(domain): add Symbol + SymbolRegistry Flyweight

Symbol identity = (venue, base, quote, market_type) tuple; native_symbol is metadata.
SymbolRegistry caches by identity, returns shared instance on repeat get().
Thread-safe via threading.Lock; concurrent asyncio test confirms identity sharing.
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 11: Market data — TradeSide, Ticker

**Files:**
- Create: `src/cryptozavr/domain/market_data.py`
- Create: `tests/unit/domain/test_market_data.py`

- [ ] **Step 1: Failing tests**

Write to `tests/unit/domain/test_market_data.py`:
```python
"""Test market data entities."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.domain.market_data import Ticker, TradeSide
from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Percentage
from cryptozavr.domain.venues import MarketType, VenueId

@pytest.fixture
def registry() -> SymbolRegistry:
    return SymbolRegistry()

@pytest.fixture
def btc_usdt(registry: SymbolRegistry) -> object:
    return registry.get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )

@pytest.fixture
def fresh_quality() -> DataQuality:
    return DataQuality(
        source=Provenance(venue_id="kucoin", endpoint="fetch_ticker"),
        fetched_at=Instant.now(),
        staleness=Staleness.FRESH,
        confidence=Confidence.HIGH,
        cache_hit=False,
    )

class TestTradeSide:
    def test_values(self) -> None:
        assert TradeSide.BUY.value == "buy"
        assert TradeSide.SELL.value == "sell"
        assert TradeSide.UNKNOWN.value == "unknown"

class TestTicker:
    def test_happy_path(self, btc_usdt, fresh_quality) -> None:
        t = Ticker(
            symbol=btc_usdt,
            last=Decimal("65000.50"),
            bid=Decimal("64999.50"),
            ask=Decimal("65001.50"),
            volume_24h=Decimal("1234.56"),
            change_24h_pct=Percentage(value=Decimal("2.5")),
            high_24h=Decimal("66000"),
            low_24h=Decimal("64000"),
            observed_at=Instant.now(),
            quality=fresh_quality,
        )
        assert t.last == Decimal("65000.50")
        assert t.bid == Decimal("64999.50")

    def test_minimal(self, btc_usdt, fresh_quality) -> None:
        t = Ticker(
            symbol=btc_usdt,
            last=Decimal("65000"),
            observed_at=Instant.now(),
            quality=fresh_quality,
        )
        assert t.bid is None
        assert t.ask is None
        assert t.volume_24h is None
```

- [ ] **Step 2: Run — must fail**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/domain/test_market_data.py -v
```

Expected: FAIL (module not found).

- [ ] **Step 3: Implement initial market_data.py**

Write to `src/cryptozavr/domain/market_data.py`:
```python
"""Market data entities: Ticker, OHLCV, OrderBook, Trades, MarketSnapshot."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from cryptozavr.domain.quality import DataQuality
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Instant, Percentage

class TradeSide(StrEnum):
    BUY = "buy"
    SELL = "sell"
    UNKNOWN = "unknown"

@dataclass(frozen=True, slots=True)
class Ticker:
    """Last price + 24h change snapshot for a single Symbol."""

    symbol: Symbol
    last: Decimal
    observed_at: Instant
    quality: DataQuality
    bid: Decimal | None = None
    ask: Decimal | None = None
    volume_24h: Decimal | None = None
    change_24h_pct: Percentage | None = None
    high_24h: Decimal | None = None
    low_24h: Decimal | None = None
```

- [ ] **Step 4: Run tests — must pass**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/domain/test_market_data.py -v
```

Expected: 4 passed (TradeSide values + 2 Ticker tests + 1 Ticker minimal).

- [ ] **Step 5: Mypy**

```bash
cd /Users/laptop/dev/cryptozavr
uv run mypy src/cryptozavr/domain/market_data.py
```

Expected: Success.

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add src/cryptozavr/domain/market_data.py tests/unit/domain/test_market_data.py
```

Write to `/tmp/commit-msg.txt`:
```text
feat(domain): add Ticker entity + TradeSide enum

Ticker: symbol, last, observed_at, quality + optional bid/ask/volume/change/high/low.
TradeSide: BUY/SELL/UNKNOWN.
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 12: Market data — OHLCVCandle + OHLCVSeries

**Files:**
- Modify: `src/cryptozavr/domain/market_data.py`
- Modify: `tests/unit/domain/test_market_data.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/unit/domain/test_market_data.py`:
```python
from cryptozavr.domain.market_data import OHLCVCandle, OHLCVSeries
from cryptozavr.domain.value_objects import Timeframe, TimeRange

def _make_candles(start_ms: int, count: int, tf_ms: int) -> tuple[OHLCVCandle, ...]:
    return tuple(
        OHLCVCandle(
            opened_at=Instant.from_ms(start_ms + i * tf_ms),
            open=Decimal("100"),
            high=Decimal("110"),
            low=Decimal("90"),
            close=Decimal("105"),
            volume=Decimal("1000"),
            closed=True,
        )
        for i in range(count)
    )

class TestOHLCVCandle:
    def test_happy_path(self) -> None:
        c = OHLCVCandle(
            opened_at=Instant.from_ms(1000),
            open=Decimal("100"),
            high=Decimal("110"),
            low=Decimal("90"),
            close=Decimal("105"),
            volume=Decimal("1000"),
            closed=True,
        )
        assert c.high == Decimal("110")

class TestOHLCVSeries:
    def test_happy_path(self, btc_usdt, fresh_quality) -> None:
        candles = _make_candles(start_ms=0, count=5, tf_ms=Timeframe.H1.to_milliseconds())
        series = OHLCVSeries(
            symbol=btc_usdt,
            timeframe=Timeframe.H1,
            candles=candles,
            range=TimeRange(start=candles[0].opened_at, end=Instant.from_ms(5 * 3_600_000)),
            quality=fresh_quality,
        )
        assert len(series.candles) == 5

    def test_last_returns_last_candle(self, btc_usdt, fresh_quality) -> None:
        candles = _make_candles(start_ms=0, count=3, tf_ms=Timeframe.H1.to_milliseconds())
        series = OHLCVSeries(
            symbol=btc_usdt, timeframe=Timeframe.H1, candles=candles,
            range=TimeRange(start=candles[0].opened_at, end=Instant.from_ms(3 * 3_600_000)),
            quality=fresh_quality,
        )
        assert series.last() is candles[-1]

    def test_window_returns_last_n(self, btc_usdt, fresh_quality) -> None:
        candles = _make_candles(start_ms=0, count=10, tf_ms=Timeframe.H1.to_milliseconds())
        series = OHLCVSeries(
            symbol=btc_usdt, timeframe=Timeframe.H1, candles=candles,
            range=TimeRange(start=candles[0].opened_at, end=Instant.from_ms(10 * 3_600_000)),
            quality=fresh_quality,
        )
        windowed = series.window(3)
        assert len(windowed.candles) == 3
        assert windowed.candles[-1] is candles[-1]

    def test_slice_by_time_range(self, btc_usdt, fresh_quality) -> None:
        candles = _make_candles(start_ms=0, count=10, tf_ms=Timeframe.H1.to_milliseconds())
        series = OHLCVSeries(
            symbol=btc_usdt, timeframe=Timeframe.H1, candles=candles,
            range=TimeRange(start=candles[0].opened_at, end=Instant.from_ms(10 * 3_600_000)),
            quality=fresh_quality,
        )
        sliced = series.slice(TimeRange(
            start=Instant.from_ms(2 * 3_600_000),
            end=Instant.from_ms(5 * 3_600_000),
        ))
        # opened_at of included candles must be in [2h, 5h)
        assert len(sliced.candles) == 3
        assert sliced.candles[0].opened_at == Instant.from_ms(2 * 3_600_000)

    def test_empty_series_last_raises(self, btc_usdt, fresh_quality) -> None:
        series = OHLCVSeries(
            symbol=btc_usdt, timeframe=Timeframe.H1, candles=(),
            range=TimeRange(start=Instant.from_ms(0), end=Instant.from_ms(1)),
            quality=fresh_quality,
        )
        with pytest.raises(IndexError):
            series.last()
```

- [ ] **Step 2: Run — must fail**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/domain/test_market_data.py -v
```

Expected: FAIL (ImportError for OHLCVCandle/OHLCVSeries).

- [ ] **Step 3: Implement**

Append to `src/cryptozavr/domain/market_data.py`:
```python
from cryptozavr.domain.value_objects import Timeframe, TimeRange

@dataclass(frozen=True, slots=True)
class OHLCVCandle:
    """Single OHLCV bar. Closed=True if the bar is settled (not an in-progress bar)."""

    opened_at: Instant
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    closed: bool = True

@dataclass(frozen=True, slots=True)
class OHLCVSeries:
    """Immutable sequence of candles for one (symbol, timeframe)."""

    symbol: Symbol
    timeframe: Timeframe
    candles: tuple[OHLCVCandle, ...]
    range: TimeRange
    quality: DataQuality

    def last(self) -> OHLCVCandle:
        """Return the most recent candle. Raises IndexError if the series is empty."""
        return self.candles[-1]

    def window(self, n: int) -> OHLCVSeries:
        """Return a new OHLCVSeries containing the last N candles.

        If N >= len(candles), returns a series with the same candles.
        """
        n = max(0, n)
        new_candles = self.candles[-n:] if n > 0 else ()
        if not new_candles:
            new_range = self.range
        else:
            new_range = TimeRange(
                start=new_candles[0].opened_at,
                end=self.range.end,
            )
        return OHLCVSeries(
            symbol=self.symbol,
            timeframe=self.timeframe,
            candles=new_candles,
            range=new_range,
            quality=self.quality,
        )

    def slice(self, tr: TimeRange) -> OHLCVSeries:
        """Return candles whose opened_at is within [tr.start, tr.end)."""
        new_candles = tuple(c for c in self.candles if tr.contains(c.opened_at))
        return OHLCVSeries(
            symbol=self.symbol,
            timeframe=self.timeframe,
            candles=new_candles,
            range=tr,
            quality=self.quality,
        )
```

- [ ] **Step 4: Run tests — must pass**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/domain/test_market_data.py -v
```

Expected: all tests pass (Ticker tests + 5 OHLCV tests).

- [ ] **Step 5: Mypy**

```bash
cd /Users/laptop/dev/cryptozavr
uv run mypy src/cryptozavr/domain/market_data.py
```

Expected: Success.

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add src/cryptozavr/domain/market_data.py tests/unit/domain/test_market_data.py
```

Write to `/tmp/commit-msg.txt`:
```text
feat(domain): add OHLCVCandle + OHLCVSeries

OHLCVCandle: opened_at, OHLCV Decimals, closed flag.
OHLCVSeries: immutable candle tuple + range + quality; methods last/window/slice
return new series without mutating.
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 13: Market data — OrderBookSnapshot

**Files:**
- Modify: `src/cryptozavr/domain/market_data.py`
- Modify: `tests/unit/domain/test_market_data.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/unit/domain/test_market_data.py`:
```python
from cryptozavr.domain.market_data import OrderBookSnapshot
from cryptozavr.domain.value_objects import PriceSize

class TestOrderBookSnapshot:
    def test_happy_path(self, btc_usdt, fresh_quality) -> None:
        bids = (
            PriceSize(price=Decimal("64999"), size=Decimal("1.0")),
            PriceSize(price=Decimal("64998"), size=Decimal("2.0")),
        )
        asks = (
            PriceSize(price=Decimal("65001"), size=Decimal("0.5")),
            PriceSize(price=Decimal("65002"), size=Decimal("1.5")),
        )
        ob = OrderBookSnapshot(
            symbol=btc_usdt, bids=bids, asks=asks,
            observed_at=Instant.now(), quality=fresh_quality,
        )
        assert ob.best_bid() == bids[0]
        assert ob.best_ask() == asks[0]

    def test_spread_and_spread_bps(self, btc_usdt, fresh_quality) -> None:
        bids = (PriceSize(price=Decimal("99900"), size=Decimal("1")),)
        asks = (PriceSize(price=Decimal("100100"), size=Decimal("1")),)
        ob = OrderBookSnapshot(
            symbol=btc_usdt, bids=bids, asks=asks,
            observed_at=Instant.now(), quality=fresh_quality,
        )
        # spread = 100100 - 99900 = 200
        assert ob.spread() == Decimal("200")
        # mid = 100000, spread_bps = 200 / 100000 * 10000 = 20
        assert ob.spread_bps() == Decimal("20")

    def test_empty_bids_or_asks(self, btc_usdt, fresh_quality) -> None:
        ob = OrderBookSnapshot(
            symbol=btc_usdt, bids=(), asks=(PriceSize(price=Decimal("1"), size=Decimal("1")),),
            observed_at=Instant.now(), quality=fresh_quality,
        )
        assert ob.best_bid() is None
        assert ob.best_ask() is not None
        assert ob.spread() is None
        assert ob.spread_bps() is None
```

- [ ] **Step 2: Run — must fail**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/domain/test_market_data.py -v
```

Expected: FAIL (ImportError for OrderBookSnapshot).

- [ ] **Step 3: Implement**

Append to `src/cryptozavr/domain/market_data.py`:
```python
from cryptozavr.domain.value_objects import PriceSize

@dataclass(frozen=True, slots=True)
class OrderBookSnapshot:
    """Single-moment order book: bids desc by price, asks asc by price."""

    symbol: Symbol
    bids: tuple[PriceSize, ...]
    asks: tuple[PriceSize, ...]
    observed_at: Instant
    quality: DataQuality

    def best_bid(self) -> PriceSize | None:
        return self.bids[0] if self.bids else None

    def best_ask(self) -> PriceSize | None:
        return self.asks[0] if self.asks else None

    def spread(self) -> Decimal | None:
        bid = self.best_bid()
        ask = self.best_ask()
        if bid is None or ask is None:
            return None
        return ask.price - bid.price

    def spread_bps(self) -> Decimal | None:
        bid = self.best_bid()
        ask = self.best_ask()
        if bid is None or ask is None:
            return None
        mid = (ask.price + bid.price) / Decimal(2)
        if mid == 0:
            return None
        return (ask.price - bid.price) / mid * Decimal(10_000)
```

- [ ] **Step 4: Run tests — must pass**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/domain/test_market_data.py -v
```

Expected: all prior + 3 OrderBook tests pass.

- [ ] **Step 5: Mypy** (same command).

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add src/cryptozavr/domain/market_data.py tests/unit/domain/test_market_data.py
```

Write to `/tmp/commit-msg.txt`:
```text
feat(domain): add OrderBookSnapshot

bids desc / asks asc. Methods: best_bid, best_ask, spread, spread_bps.
Handles empty-side gracefully (returns None).
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 14: Market data — TradeTick + MarketSnapshot

**Files:**
- Modify: `src/cryptozavr/domain/market_data.py`
- Modify: `tests/unit/domain/test_market_data.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/unit/domain/test_market_data.py`:
```python
from cryptozavr.domain.market_data import MarketSnapshot, TradeTick

class TestTradeTick:
    def test_happy_path(self, btc_usdt) -> None:
        t = TradeTick(
            symbol=btc_usdt,
            price=Decimal("65000"),
            size=Decimal("0.1"),
            side=TradeSide.BUY,
            executed_at=Instant.now(),
        )
        assert t.side == TradeSide.BUY

class TestMarketSnapshot:
    def test_happy_path(self, btc_usdt, fresh_quality) -> None:
        ticker = Ticker(
            symbol=btc_usdt,
            last=Decimal("65000"),
            observed_at=Instant.now(),
            quality=fresh_quality,
        )
        ob = OrderBookSnapshot(
            symbol=btc_usdt,
            bids=(PriceSize(price=Decimal("64999"), size=Decimal("1")),),
            asks=(PriceSize(price=Decimal("65001"), size=Decimal("1")),),
            observed_at=Instant.now(), quality=fresh_quality,
        )
        snap = MarketSnapshot(
            symbol=btc_usdt,
            ticker=ticker,
            orderbook=ob,
            ohlcv={},
            recent_trades=(),
        )
        assert snap.ticker is ticker
        assert snap.orderbook is ob

    def test_minimal_snapshot(self, btc_usdt, fresh_quality) -> None:
        ticker = Ticker(
            symbol=btc_usdt, last=Decimal("65000"),
            observed_at=Instant.now(), quality=fresh_quality,
        )
        snap = MarketSnapshot(symbol=btc_usdt, ticker=ticker)
        assert snap.orderbook is None
        assert snap.ohlcv == {}
        assert snap.recent_trades == ()
```

- [ ] **Step 2: Run — must fail**.

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/domain/test_market_data.py -v
```

- [ ] **Step 3: Implement**

Append to `src/cryptozavr/domain/market_data.py`:
```python
@dataclass(frozen=True, slots=True)
class TradeTick:
    """Single executed trade."""

    symbol: Symbol
    price: Decimal
    size: Decimal
    side: TradeSide
    executed_at: Instant
    trade_id: str | None = None

@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    """Composite: ticker + orderbook + ohlcv + recent trades for one Symbol."""

    symbol: Symbol
    ticker: Ticker
    orderbook: OrderBookSnapshot | None = None
    ohlcv: dict[Timeframe, OHLCVSeries] = field(default_factory=dict)
    recent_trades: tuple[TradeTick, ...] = field(default_factory=tuple)
```

- [ ] **Step 4: Run — must pass**.

- [ ] **Step 5: Mypy**.

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add src/cryptozavr/domain/market_data.py tests/unit/domain/test_market_data.py
```

Write to `/tmp/commit-msg.txt`:
```text
feat(domain): add TradeTick + MarketSnapshot composite

TradeTick: symbol, price, size, side, executed_at, optional trade_id.
MarketSnapshot: ticker + optional orderbook + ohlcv dict + recent trades.
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 15: Protocol interfaces — MarketDataProvider, Repository, Clock

**Files:**
- Create: `src/cryptozavr/domain/interfaces.py`
- Create: `tests/unit/domain/test_interfaces.py`

- [ ] **Step 1: Failing tests**

Write to `tests/unit/domain/test_interfaces.py`:
```python
"""Test Protocol structural subtyping for domain interfaces."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.domain.interfaces import (
    Clock,
    MarketDataProvider,
    Repository,
)
from cryptozavr.domain.market_data import (
    OrderBookSnapshot,
    Ticker,
    TradeTick,
)
from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.symbols import Symbol, SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Timeframe
from cryptozavr.domain.venues import MarketType, VenueId

class _FakeProvider:
    """Minimal concrete impl for structural subtyping check."""

    venue_id = VenueId.KUCOIN

    async def load_markets(self) -> None:  # pragma: no cover - not exercised
        pass

    async def fetch_ticker(self, symbol: Symbol) -> Ticker:
        return Ticker(
            symbol=symbol, last=Decimal("1"),
            observed_at=Instant.now(),
            quality=DataQuality(
                source=Provenance(venue_id="kucoin", endpoint="fetch_ticker"),
                fetched_at=Instant.now(),
                staleness=Staleness.FRESH,
                confidence=Confidence.HIGH,
                cache_hit=False,
            ),
        )

    async def fetch_ohlcv(  # pragma: no cover
        self, symbol: Symbol, timeframe: Timeframe,
        since: Instant | None = None, limit: int = 500,
    ) -> object:
        return None

    async def fetch_order_book(  # pragma: no cover
        self, symbol: Symbol, depth: int = 50,
    ) -> OrderBookSnapshot:
        raise NotImplementedError

    async def fetch_trades(  # pragma: no cover
        self, symbol: Symbol, since: Instant | None = None, limit: int = 100,
    ) -> tuple[TradeTick, ...]:
        return ()

    async def close(self) -> None:  # pragma: no cover
        pass

class _FakeRepo:
    async def get(self, key: object) -> object | None:
        return None

    async def put(self, entity: object) -> None:
        pass

    async def list(self, **filters: object) -> list[object]:
        return []

class _FakeClock:
    def now(self) -> Instant:
        return Instant.now()

def test_FakeProvider_conforms_to_MarketDataProvider() -> None:
    provider: MarketDataProvider = _FakeProvider()  # should type-check
    assert provider.venue_id == VenueId.KUCOIN

def test_FakeRepo_conforms_to_Repository() -> None:
    repo: Repository[object] = _FakeRepo()  # should type-check
    assert repo is not None

def test_FakeClock_conforms_to_Clock() -> None:
    clock: Clock = _FakeClock()  # should type-check
    assert isinstance(clock.now(), Instant)
```

- [ ] **Step 2: Run — must fail**.

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/domain/test_interfaces.py -v
```

Expected: FAIL (module not found).

- [ ] **Step 3: Implement**

Write to `src/cryptozavr/domain/interfaces.py`:
```python
"""Protocol interfaces for domain-level dependencies.

Concrete implementations live in L2 (Infrastructure). L3/L4 depend only on Protocols.
"""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from cryptozavr.domain.market_data import (
    OHLCVSeries,
    OrderBookSnapshot,
    Ticker,
    TradeTick,
)
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Instant, Timeframe
from cryptozavr.domain.venues import VenueId

T = TypeVar("T")

@runtime_checkable
class MarketDataProvider(Protocol):
    """Read-only market data provider.

    Implementations in infrastructure.providers translate vendor-specific APIs
    into these Domain methods. All methods are async.
    """

    venue_id: VenueId

    async def load_markets(self) -> None: ...

    async def fetch_ticker(self, symbol: Symbol) -> Ticker: ...

    async def fetch_ohlcv(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        since: Instant | None = None,
        limit: int = 500,
    ) -> OHLCVSeries: ...

    async def fetch_order_book(
        self, symbol: Symbol, depth: int = 50,
    ) -> OrderBookSnapshot: ...

    async def fetch_trades(
        self,
        symbol: Symbol,
        since: Instant | None = None,
        limit: int = 100,
    ) -> tuple[TradeTick, ...]: ...

    async def close(self) -> None: ...

@runtime_checkable
class Repository(Protocol[T]):
    """Generic aggregate-root repository. Concrete impls in infrastructure.repositories."""

    async def get(self, key: object) -> T | None: ...

    async def put(self, entity: T) -> None: ...

    async def list(self, **filters: object) -> list[T]: ...

@runtime_checkable
class Clock(Protocol):
    """Injectable time source for testability (FrozenClock in tests)."""

    def now(self) -> Instant: ...
```

- [ ] **Step 4: Run — must pass**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/domain/test_interfaces.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Mypy**

```bash
cd /Users/laptop/dev/cryptozavr
uv run mypy src/cryptozavr/domain/interfaces.py
```

Expected: Success.

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add src/cryptozavr/domain/interfaces.py tests/unit/domain/test_interfaces.py
```

Write to `/tmp/commit-msg.txt`:
```text
feat(domain): add MarketDataProvider/Repository/Clock Protocols

MarketDataProvider: load_markets, fetch_ticker/ohlcv/order_book/trades, close.
Repository[T]: get/put/list. Clock: now. All runtime_checkable via @Protocol.
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 16: Full domain verification + coverage report

**Files:** none — verification task.

- [ ] **Step 1: Full test suite run**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/ -v --cov=cryptozavr.domain --cov-report=term-missing
```

Expected: all tests pass. Coverage on `src/cryptozavr/domain/` ≥ 95%.

If any coverage lines unexpectedly missed — add targeted tests. If coverage is below 95% for reasons unrelated to the spec (e.g. defensive branches that can't be hit), note in report.

- [ ] **Step 2: Full mypy run**

```bash
cd /Users/laptop/dev/cryptozavr
uv run mypy src/cryptozavr/domain
```

Expected: Success.

- [ ] **Step 3: Full lint run**

```bash
cd /Users/laptop/dev/cryptozavr
uv run ruff check src/cryptozavr/domain tests/unit/domain
uv run ruff format --check src/cryptozavr/domain tests/unit/domain
```

Expected: zero errors.

- [ ] **Step 4: Pre-commit all files**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pre-commit run --all-files
```

Expected: all pass.

- [ ] **Step 5: Verify package importability**

```bash
cd /Users/laptop/dev/cryptozavr
uv run python -c "
from cryptozavr.domain.exceptions import DomainError, SymbolNotFoundError
from cryptozavr.domain.value_objects import Timeframe, Instant, TimeRange, Money, Percentage, PriceSize
from cryptozavr.domain.quality import Staleness, Confidence, Provenance, DataQuality
from cryptozavr.domain.assets import Asset, AssetCategory
from cryptozavr.domain.venues import Venue, VenueId, VenueKind, MarketType, VenueCapability, VenueStateKind
from cryptozavr.domain.symbols import Symbol, SymbolRegistry
from cryptozavr.domain.market_data import Ticker, OHLCVCandle, OHLCVSeries, OrderBookSnapshot, TradeTick, TradeSide, MarketSnapshot
from cryptozavr.domain.interfaces import MarketDataProvider, Repository, Clock
print('all domain imports OK')
"
```

Expected: `all domain imports OK`.

**No commit** — verification only.

---

### Task 17: Tag v0.0.2 + update CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Verify git clean**

```bash
cd /Users/laptop/dev/cryptozavr
git status
```

Expected: `nothing to commit, working tree clean`. If not — report BLOCKED.

- [ ] **Step 2: Update CHANGELOG**

Open `/Users/laptop/dev/cryptozavr/CHANGELOG.md`. Find the `## [Unreleased]` header. Replace:

```markdown
## [Unreleased]
```

with:

```markdown
## [Unreleased]

## [0.0.2] - 2026-04-21

### Added — M2.1 Domain layer
- Value objects: `Timeframe`, `Instant`, `TimeRange`, `Money`, `Percentage`, `PriceSize`.
- Quality types: `Staleness` (ordered FRESH<RECENT<STALE<EXPIRED), `Confidence`, `Provenance`, `DataQuality` envelope.
- Entities: `Asset` + `AssetCategory`, `Venue` + 5 enums, `Symbol` + `SymbolRegistry` (Flyweight).
- Market data: `Ticker`, `OHLCVCandle`, `OHLCVSeries` (with slice/window), `OrderBookSnapshot` (with spread/spread_bps), `TradeTick`, `TradeSide`, `MarketSnapshot` composite.
- Protocol interfaces: `MarketDataProvider`, `Repository[T]`, `Clock`.
- Exception hierarchy: `DomainError` root + 4 families (ValidationError, NotFoundError, ProviderError, QualityError) with domain-specific subtypes.
- Dev deps: `hypothesis`, `polyfactory` for property-based and factory-driven tests.
- ~100 unit tests, domain coverage ≥ 95%.
```

- [ ] **Step 3: Commit CHANGELOG**

```bash
cd /Users/laptop/dev/cryptozavr
git add CHANGELOG.md
```

Write to `/tmp/commit-msg.txt`:
```bash
docs: finalize CHANGELOG for v0.0.2 (M2.1 Domain layer)
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

- [ ] **Step 4: Create annotated tag**

```bash
cd /Users/laptop/dev/cryptozavr
git tag -a v0.0.2 -m "M2.1 Domain layer complete

Pure Pydantic/dataclass models: value objects, entities, quality envelope,
Protocol interfaces, exception hierarchy. Flyweight SymbolRegistry.
No I/O, no async, 100+ unit tests, coverage ≥ 95%.
Ready for M2.2 (Supabase schema + Gateway)."
```

- [ ] **Step 5: Final summary**

```bash
cd /Users/laptop/dev/cryptozavr
echo "=== M2.1 Domain layer complete ==="
git log --oneline v0.0.1..HEAD
echo ""
git tag -l
echo ""
uv run python -c "from cryptozavr.domain.market_data import MarketSnapshot; print('Domain OK')"
```

Expected: list of M2.1 commits, tags `v0.0.1` + `v0.0.2`, "Domain OK".

**Do not push.** Git remote still deferred until email-verified.

---

## Acceptance Criteria for M2.1

1. ✅ All 17 tasks executed.
2. ✅ `uv run pytest tests/ -v` — all unit tests pass (M1 tests + ~100 new M2.1 tests).
3. ✅ Coverage on `src/cryptozavr/domain/` ≥ 95%.
4. ✅ `uv run mypy src/cryptozavr/domain` — Success.
5. ✅ `uv run ruff check src/cryptozavr/domain tests/unit/domain` — zero errors.
6. ✅ All 8 domain modules import cleanly via top-level script.
7. ✅ `SymbolRegistry.get()` concurrent-safe: 100 parallel `asyncio.gather` calls return `is`-identical instances.
8. ✅ Exception hierarchy: every concrete exception in `exceptions.py` descends from `DomainError`.
9. ✅ No I/O in domain: `grep -r "import httpx\|import ccxt\|import asyncpg\|import supabase\|from fastmcp" src/cryptozavr/domain/` returns no hits.
10. ✅ Git tag `v0.0.2` at HEAD.

---

## Handoff to M2.2

After M2.1 complete:

1. Invoke `writing-plans` with context: "M2.1 Domain complete. Write plan for M2.2 Supabase schema + Gateway based on MVP spec section 5."
2. M2.2 scope: 6 Supabase migrations, `SupabaseGateway` (Facade over asyncpg + supabase-py + realtime-py), `mappers` (rows → Domain entities), integration tests requiring `supabase start`.

---

## Notes

- **TDD throughout.** Every Task follows red → green → commit. Not optional.
- **One file, one responsibility.** If a file grows beyond ~150 lines during implementation, pause and report. The biggest domain file (`market_data.py`) will reach ~120 lines; that's the upper limit.
- **Flyweight concurrency.** `SymbolRegistry` uses `threading.Lock`, not `asyncio.Lock`, because it's called from sync constructors and works correctly under the GIL + asyncio. The async concurrent test verifies identity preservation.
- **`total_ordering` on Staleness.** We use an ordering table rather than IntEnum to keep the API StrEnum-like (`.value` returns "fresh" etc.), while still supporting `<`/`>` comparisons.
- **`Asset` and `Venue` use `eq=False`** in `@dataclass` so we can override `__eq__`/`__hash__` to use only identity fields (code / id), not metadata.
