# Paper Trading Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ad-hoc Bash ledger with a first-class Supabase-backed paper-trading subsystem. Trades persist, auto-start a watch, auto-close on terminal events, survive server restarts, and broadcast via Supabase Realtime.

**Architecture:** Three-layer (domain + application + infra) plus MCP surface. `PaperLedgerService` sits between `PaperTradeRepository` (asyncpg → `cryptozavr.paper_trades`) and `PositionWatcher`; it registers an `on_terminal` callback so every watch terminal event becomes an atomic DB close. Resume-on-startup rebuilds live watches for `status='running'` rows.

**Tech Stack:** Python 3.12, FastMCP 3.2.4+, asyncpg, Supabase Postgres + Realtime, Pydantic v2, pytest.

**Spec:** `docs/superpowers/specs/2026-04-22-paper-trading-ledger-design.md`

---

## File Structure

### New files

- `src/cryptozavr/domain/paper.py` — `PaperSide`, `PaperStatus`, `PaperTrade`, `PaperStats` (frozen/mutable dataclasses).
- `src/cryptozavr/infrastructure/persistence/paper_trade_repo.py` — `PaperTradeRepository` (asyncpg CRUD + stats view read).
- `src/cryptozavr/application/services/paper_ledger_service.py` — `PaperLedgerService` (open/close/cancel/reset + `on_terminal` callback + `resume_open_watches`).
- `src/cryptozavr/mcp/tools/paper.py` — five MCP tools.
- `src/cryptozavr/mcp/resources/paper.py` — four MCP resources.
- `src/cryptozavr/mcp/prompts/paper.py` — three MCP prompts.
- `supabase/migrations/00000000000090_paper_trades.sql` — table + view + publication line.
- `tests/unit/domain/test_paper.py`
- `tests/unit/application/services/test_paper_ledger_service.py`
- `tests/unit/mcp/tools/test_paper_tools.py`
- `tests/integration/test_paper_ledger_live.py`

### Modified files

- `src/cryptozavr/domain/exceptions.py` — add `TradeNotFoundError`.
- `src/cryptozavr/application/services/position_watcher.py` — add `on_terminal` param to `PositionWatcher.start()` and plumb into `_run`.
- `src/cryptozavr/mcp/dtos.py` — add `PaperTradeDTO`, `PaperStatsDTO`.
- `src/cryptozavr/mcp/lifespan_state.py` — `paper_ledger`, `paper_bankroll_override` keys + getter.
- `src/cryptozavr/mcp/bootstrap.py` — init `PaperTradeRepository`, `PaperLedgerService`, call `resume_open_watches()`.
- `src/cryptozavr/mcp/server.py` — register new tools/resources/prompts.
- `src/cryptozavr/mcp/settings.py` — `paper_bankroll_initial: Decimal = 10000`.
- `CHANGELOG.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `pyproject.toml`, `src/cryptozavr/__init__.py` — version bump 0.3.5 → 0.4.0.

---

## Task 1: Domain types + TradeNotFoundError

**Files:**
- Create: `src/cryptozavr/domain/paper.py`
- Modify: `src/cryptozavr/domain/exceptions.py`
- Test: `tests/unit/domain/test_paper.py`

- [ ] **Step 1.1: Write failing tests**

```python
# tests/unit/domain/test_paper.py
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from cryptozavr.domain.exceptions import TradeNotFoundError, ValidationError
from cryptozavr.domain.paper import (
    PaperSide,
    PaperStats,
    PaperStatus,
    PaperTrade,
)

class TestPaperEnums:
    def test_side_values(self) -> None:
        assert PaperSide.LONG.value == "long"
        assert PaperSide.SHORT.value == "short"

    def test_status_values(self) -> None:
        assert PaperStatus.RUNNING.value == "running"
        assert PaperStatus.CLOSED.value == "closed"
        assert PaperStatus.ABANDONED.value == "abandoned"

class TestPaperTrade:
    def _base_args(self) -> dict:
        return {
            "id": uuid4(),
            "side": PaperSide.LONG,
            "venue": "kucoin",
            "symbol_native": "BTC-USDT",
            "entry": Decimal("100"),
            "stop": Decimal("95"),
            "take": Decimal("110"),
            "size_quote": Decimal("1000"),
            "opened_at_ms": 1_000_000,
            "max_duration_sec": 3600,
            "status": PaperStatus.RUNNING,
        }

    def test_valid_long(self) -> None:
        trade = PaperTrade(**self._base_args())
        assert trade.status is PaperStatus.RUNNING
        assert trade.exit_price is None
        assert trade.pnl_quote is None

    def test_long_requires_stop_below_entry(self) -> None:
        args = self._base_args() | {"stop": Decimal("105")}
        with pytest.raises(ValidationError, match="stop < entry"):
            PaperTrade(**args)

    def test_short_requires_take_below_entry(self) -> None:
        args = self._base_args() | {
            "side": PaperSide.SHORT,
            "stop": Decimal("110"),
            "take": Decimal("105"),
        }
        with pytest.raises(ValidationError, match="take < entry"):
            PaperTrade(**args)

    def test_size_must_be_positive(self) -> None:
        args = self._base_args() | {"size_quote": Decimal("0")}
        with pytest.raises(ValidationError, match="size_quote"):
            PaperTrade(**args)

    def test_compute_pnl_long_profit(self) -> None:
        # entry=100, exit=110, size_quote=1000 -> qty=10, pnl = (110-100)*10 = 100
        trade = PaperTrade(**self._base_args())
        pnl = trade.compute_pnl(exit_price=Decimal("110"))
        assert pnl == Decimal("100.00")

    def test_compute_pnl_long_loss(self) -> None:
        # entry=100, exit=95, size_quote=1000 -> qty=10, pnl = -50
        trade = PaperTrade(**self._base_args())
        pnl = trade.compute_pnl(exit_price=Decimal("95"))
        assert pnl == Decimal("-50.00")

    def test_compute_pnl_short_profit(self) -> None:
        # entry=100, exit=95, short -> pnl = (100-95)*10 = 50
        args = self._base_args() | {
            "side": PaperSide.SHORT,
            "stop": Decimal("105"),
            "take": Decimal("90"),
        }
        trade = PaperTrade(**args)
        pnl = trade.compute_pnl(exit_price=Decimal("95"))
        assert pnl == Decimal("50.00")

class TestTradeNotFoundError:
    def test_message(self) -> None:
        tid = uuid4()
        exc = TradeNotFoundError(trade_id=str(tid))
        assert str(tid) in str(exc)
        assert exc.trade_id == str(tid)

class TestPaperStats:
    def test_construction(self) -> None:
        stats = PaperStats(
            trades_count=5,
            wins=3,
            losses=2,
            open_count=1,
            net_pnl_quote=Decimal("12.5"),
            avg_win_quote=Decimal("10"),
            avg_loss_quote=Decimal("-5"),
        )
        assert stats.win_rate == Decimal("0.6")
```

- [ ] **Step 1.2: Verify tests fail**

```bash
uv run pytest tests/unit/domain/test_paper.py -v
```
Expected: FAIL — `cryptozavr.domain.paper` does not exist.

- [ ] **Step 1.3: Add TradeNotFoundError to exceptions**

In `src/cryptozavr/domain/exceptions.py`, append after the other `NotFoundError` subclasses:

```python
class TradeNotFoundError(NotFoundError):
    """Raised when a paper trade id does not exist."""

    def __init__(self, trade_id: str) -> None:
        super().__init__(f"Trade not found: {trade_id!r}")
        self.trade_id = trade_id
```

- [ ] **Step 1.4: Implement `domain/paper.py`**

```python
# src/cryptozavr/domain/paper.py
"""Paper trading domain types.

PaperTrade is immutable (frozen). Mutations are represented as NEW
instances returned from repository operations; the DB is the source
of truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from cryptozavr.domain.exceptions import ValidationError

class PaperSide(StrEnum):
    LONG = "long"
    SHORT = "short"

class PaperStatus(StrEnum):
    RUNNING = "running"
    CLOSED = "closed"
    ABANDONED = "abandoned"

_QUANT = Decimal("0.01")

@dataclass(frozen=True, slots=True)
class PaperTrade:
    id: UUID
    side: PaperSide
    venue: str
    symbol_native: str
    entry: Decimal
    stop: Decimal
    take: Decimal
    size_quote: Decimal
    opened_at_ms: int
    max_duration_sec: int
    status: PaperStatus
    exit_price: Decimal | None = None
    closed_at_ms: int | None = None
    pnl_quote: Decimal | None = None
    reason: str | None = None
    watch_id: str | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        if self.entry <= 0 or self.stop <= 0 or self.take <= 0:
            raise ValidationError("entry/stop/take must be positive")
        if self.size_quote <= 0:
            raise ValidationError("size_quote must be positive")
        if self.side is PaperSide.LONG:
            if not (self.stop < self.entry):
                raise ValidationError("long: stop < entry required")
            if not (self.entry < self.take):
                raise ValidationError("long: entry < take required")
        else:
            if not (self.take < self.entry):
                raise ValidationError("short: take < entry required")
            if not (self.entry < self.stop):
                raise ValidationError("short: entry < stop required")

    def compute_pnl(self, *, exit_price: Decimal) -> Decimal:
        """Compute pnl in quote currency for a given exit price."""
        qty = self.size_quote / self.entry
        if self.side is PaperSide.LONG:
            delta = exit_price - self.entry
        else:
            delta = self.entry - exit_price
        return (delta * qty).quantize(_QUANT)

@dataclass(frozen=True, slots=True)
class PaperStats:
    trades_count: int
    wins: int
    losses: int
    open_count: int
    net_pnl_quote: Decimal
    avg_win_quote: Decimal
    avg_loss_quote: Decimal

    @property
    def win_rate(self) -> Decimal:
        if self.trades_count == 0:
            return Decimal("0")
        return (Decimal(self.wins) / Decimal(self.trades_count)).quantize(
            Decimal("0.0001")
        )
```

- [ ] **Step 1.5: Verify tests pass**

```bash
uv run pytest tests/unit/domain/test_paper.py -v
```
Expected: all pass.

- [ ] **Step 1.6: Lint + mypy**

```bash
uv run ruff check src/cryptozavr/domain/paper.py src/cryptozavr/domain/exceptions.py tests/unit/domain/test_paper.py
uv run ruff format --check src/cryptozavr/domain/paper.py src/cryptozavr/domain/exceptions.py tests/unit/domain/test_paper.py
uv run mypy src/cryptozavr/domain/paper.py src/cryptozavr/domain/exceptions.py
```

- [ ] **Step 1.7: Commit**

Write `/tmp/commit-msg.txt`:

```bash
feat(domain): add paper trading types + TradeNotFoundError

Frozen PaperTrade with side/price invariants, compute_pnl helper,
PaperStats with derived win_rate, TradeNotFoundError for MCP tools.
```

```bash
git add src/cryptozavr/domain/paper.py src/cryptozavr/domain/exceptions.py tests/unit/domain/test_paper.py
git commit -F /tmp/commit-msg.txt && rm /tmp/commit-msg.txt
```

---

## Task 2: Migration + Realtime publication

**Files:**
- Create: `supabase/migrations/00000000000090_paper_trades.sql`

- [ ] **Step 2.1: Write the migration**

```sql
-- supabase/migrations/00000000000090_paper_trades.sql
-- Paper trading ledger: one row per trade, insert-then-update lifecycle.
-- Terminal events and manual closes go through atomic
-- UPDATE ... WHERE status = 'running' to be idempotent under races.

create table cryptozavr.paper_trades (
  id              uuid primary key default gen_random_uuid(),
  side            text not null check (side in ('long', 'short')),
  venue           text not null,
  symbol_native   text not null,
  entry           numeric(20, 8) not null check (entry > 0),
  stop            numeric(20, 8) not null check (stop > 0),
  take            numeric(20, 8) not null check (take > 0),
  size_quote      numeric(20, 8) not null check (size_quote > 0),
  opened_at_ms    bigint not null,
  max_duration_sec integer not null,
  status          text not null check (status in ('running', 'closed', 'abandoned')),
  exit_price      numeric(20, 8),
  closed_at_ms    bigint,
  pnl_quote       numeric(20, 8),
  reason          text,
  watch_id        text,
  note            text
);

create index paper_trades_running
  on cryptozavr.paper_trades (status)
  where status = 'running';

create index paper_trades_opened_desc
  on cryptozavr.paper_trades (opened_at_ms desc);

create index paper_trades_watch_id
  on cryptozavr.paper_trades (watch_id)
  where watch_id is not null;

alter table cryptozavr.paper_trades enable row level security;

create policy service_role_all on cryptozavr.paper_trades
  for all to service_role using (true) with check (true);

create or replace view cryptozavr.paper_stats as
select
  count(*) filter (where status = 'closed')                    as trades_count,
  count(*) filter (where status = 'closed' and pnl_quote > 0)  as wins,
  count(*) filter (where status = 'closed' and pnl_quote <= 0) as losses,
  count(*) filter (where status = 'running')                   as open_count,
  coalesce(sum(pnl_quote) filter (where status = 'closed'), 0) as net_pnl_quote,
  coalesce(avg(pnl_quote) filter (where status = 'closed' and pnl_quote > 0), 0)
    as avg_win_quote,
  coalesce(avg(pnl_quote) filter (where status = 'closed' and pnl_quote <= 0), 0)
    as avg_loss_quote
from cryptozavr.paper_trades;

-- Broadcast lifecycle to Supabase Realtime.
alter publication supabase_realtime add table cryptozavr.paper_trades;
```

- [ ] **Step 2.2: Apply the migration against live Supabase**

Run:

```bash
supabase db push
```

Expected: migration applied; `paper_trades` table and `paper_stats` view appear in the `cryptozavr` schema.

- [ ] **Step 2.3: Sanity verify**

```bash
uv run python -c "
import asyncio, asyncpg, os
async def main():
    conn = await asyncpg.connect(os.environ['SUPABASE_DB_URL'])
    rows = await conn.fetch(\"select * from cryptozavr.paper_stats\")
    print('paper_stats rows:', rows)
    await conn.close()
asyncio.run(main())
"
```

Expected output: one row with all zeros.

- [ ] **Step 2.4: Commit**

`/tmp/commit-msg.txt`:

```bash
feat(db): add paper_trades table + paper_stats view

Insert-then-update lifecycle, partial index for status='running',
service_role RLS policy, join supabase_realtime publication so
consumers can react without polling.
```

```bash
git add supabase/migrations/00000000000090_paper_trades.sql
git commit -F /tmp/commit-msg.txt && rm /tmp/commit-msg.txt
```

---

## Task 3: PaperTradeRepository

**Files:**
- Create: `src/cryptozavr/infrastructure/persistence/paper_trade_repo.py`
- Test: `tests/contract/test_paper_trade_repo.py`

- [ ] **Step 3.1: Write contract tests (integration-style against live Supabase)**

```python
# tests/contract/test_paper_trade_repo.py
"""Contract tests: PaperTradeRepository against live Supabase.

Skipped if SUPABASE_DB_URL is missing or SKIP_SUPABASE_TESTS=1.
"""

from __future__ import annotations

import os
from decimal import Decimal
from uuid import uuid4

import asyncpg
import pytest

from cryptozavr.domain.paper import PaperSide, PaperStatus, PaperTrade
from cryptozavr.infrastructure.persistence.paper_trade_repo import (
    PaperTradeRepository,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("SKIP_SUPABASE_TESTS") == "1" or not os.getenv("SUPABASE_DB_URL"),
        reason="live Supabase tests disabled",
    ),
]

async def _build_repo() -> tuple[PaperTradeRepository, asyncpg.Pool]:
    pool = await asyncpg.create_pool(os.environ["SUPABASE_DB_URL"], min_size=1, max_size=2)
    await pool.execute("truncate cryptozavr.paper_trades")
    return PaperTradeRepository(pool=pool), pool

def _sample_trade() -> PaperTrade:
    return PaperTrade(
        id=uuid4(),
        side=PaperSide.LONG,
        venue="kucoin",
        symbol_native="BTC-USDT",
        entry=Decimal("100"),
        stop=Decimal("95"),
        take=Decimal("110"),
        size_quote=Decimal("1000"),
        opened_at_ms=1_000_000,
        max_duration_sec=3600,
        status=PaperStatus.RUNNING,
    )

async def test_insert_fetch_roundtrip() -> None:
    repo, pool = await _build_repo()
    try:
        trade = _sample_trade()
        await repo.insert(trade)
        got = await repo.fetch_by_id(str(trade.id))
        assert got is not None
        assert got.id == trade.id
        assert got.status is PaperStatus.RUNNING
        assert got.watch_id is None
    finally:
        await pool.close()

async def test_set_watch_id() -> None:
    repo, pool = await _build_repo()
    try:
        trade = _sample_trade()
        await repo.insert(trade)
        await repo.set_watch_id(str(trade.id), "watch-abc")
        got = await repo.fetch_by_id(str(trade.id))
        assert got is not None
        assert got.watch_id == "watch-abc"
    finally:
        await pool.close()

async def test_close_atomic() -> None:
    repo, pool = await _build_repo()
    try:
        trade = _sample_trade()
        await repo.insert(trade)
        rowcount = await repo.close(
            trade_id=str(trade.id),
            exit_price=Decimal("110"),
            closed_at_ms=1_100_000,
            pnl_quote=Decimal("100"),
            reason="take_hit",
        )
        assert rowcount == 1
        # Second close is no-op (already closed).
        rowcount2 = await repo.close(
            trade_id=str(trade.id),
            exit_price=Decimal("105"),
            closed_at_ms=1_200_000,
            pnl_quote=Decimal("50"),
            reason="manual_cancel",
        )
        assert rowcount2 == 0
        got = await repo.fetch_by_id(str(trade.id))
        assert got is not None
        assert got.status is PaperStatus.CLOSED
        assert got.reason == "take_hit"
        assert got.pnl_quote == Decimal("100")
    finally:
        await pool.close()

async def test_fetch_open() -> None:
    repo, pool = await _build_repo()
    try:
        t1 = _sample_trade()
        t2 = _sample_trade()
        await repo.insert(t1)
        await repo.insert(t2)
        await repo.close(
            trade_id=str(t1.id),
            exit_price=Decimal("110"),
            closed_at_ms=1_100_000,
            pnl_quote=Decimal("100"),
            reason="take_hit",
        )
        open_trades = await repo.fetch_open()
        assert len(open_trades) == 1
        assert open_trades[0].id == t2.id
    finally:
        await pool.close()

async def test_stats_view() -> None:
    repo, pool = await _build_repo()
    try:
        # 2 closed trades: one winner, one loser. 1 running.
        for pnl, reason in [(Decimal("50"), "take_hit"), (Decimal("-30"), "stop_hit")]:
            trade = _sample_trade()
            await repo.insert(trade)
            await repo.close(
                trade_id=str(trade.id),
                exit_price=Decimal("100"),  # placeholder — only pnl matters for stats
                closed_at_ms=1_100_000,
                pnl_quote=pnl,
                reason=reason,
            )
        await repo.insert(_sample_trade())  # running
        stats = await repo.stats()
        assert stats.trades_count == 2
        assert stats.wins == 1
        assert stats.losses == 1
        assert stats.open_count == 1
        assert stats.net_pnl_quote == Decimal("20")
    finally:
        await pool.close()

async def test_truncate_removes_all() -> None:
    repo, pool = await _build_repo()
    try:
        await repo.insert(_sample_trade())
        await repo.truncate()
        open_trades = await repo.fetch_open()
        assert open_trades == []
    finally:
        await pool.close()
```

- [ ] **Step 3.2: Verify tests fail**

```bash
uv run pytest tests/contract/test_paper_trade_repo.py -v
```
Expected: FAIL (module missing).

- [ ] **Step 3.3: Implement repository**

```python
# src/cryptozavr/infrastructure/persistence/paper_trade_repo.py
"""PaperTradeRepository: asyncpg persistence for cryptozavr.paper_trades."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import asyncpg

from cryptozavr.domain.paper import (
    PaperSide,
    PaperStats,
    PaperStatus,
    PaperTrade,
)

class PaperTradeRepository:
    """CRUD for cryptozavr.paper_trades plus stats-view read."""

    def __init__(self, *, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def insert(self, trade: PaperTrade) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                insert into cryptozavr.paper_trades
                  (id, side, venue, symbol_native, entry, stop, take,
                   size_quote, opened_at_ms, max_duration_sec, status,
                   exit_price, closed_at_ms, pnl_quote, reason,
                   watch_id, note)
                values ($1, $2, $3, $4, $5, $6, $7,
                        $8, $9, $10, $11,
                        $12, $13, $14, $15,
                        $16, $17)
                """,
                trade.id,
                trade.side.value,
                trade.venue,
                trade.symbol_native,
                trade.entry,
                trade.stop,
                trade.take,
                trade.size_quote,
                trade.opened_at_ms,
                trade.max_duration_sec,
                trade.status.value,
                trade.exit_price,
                trade.closed_at_ms,
                trade.pnl_quote,
                trade.reason,
                trade.watch_id,
                trade.note,
            )

    async def set_watch_id(self, trade_id: str, watch_id: str | None) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "update cryptozavr.paper_trades set watch_id = $1 where id = $2",
                watch_id,
                UUID(trade_id),
            )

    async def close(
        self,
        *,
        trade_id: str,
        exit_price: Decimal,
        closed_at_ms: int,
        pnl_quote: Decimal,
        reason: str,
        target_status: PaperStatus = PaperStatus.CLOSED,
    ) -> int:
        """Atomic close — returns rowcount (1 on success, 0 if not running)."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                update cryptozavr.paper_trades
                set status = $1,
                    exit_price = $2,
                    closed_at_ms = $3,
                    pnl_quote = $4,
                    reason = $5
                where id = $6 and status = 'running'
                """,
                target_status.value,
                exit_price,
                closed_at_ms,
                pnl_quote,
                reason,
                UUID(trade_id),
            )
        # asyncpg returns 'UPDATE N'
        return int(result.split()[-1])

    async def mark_abandoned(self, trade_id: str, reason: str) -> int:
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                update cryptozavr.paper_trades
                set status = 'abandoned', reason = $1
                where id = $2 and status = 'running'
                """,
                reason,
                UUID(trade_id),
            )
        return int(result.split()[-1])

    async def fetch_by_id(self, trade_id: str) -> PaperTrade | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "select * from cryptozavr.paper_trades where id = $1",
                UUID(trade_id),
            )
        return _row_to_trade(row) if row else None

    async def fetch_open(self) -> list[PaperTrade]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "select * from cryptozavr.paper_trades where status = 'running'"
                " order by opened_at_ms desc"
            )
        return [_row_to_trade(r) for r in rows]

    async def fetch_page(self, limit: int = 200, offset: int = 0) -> list[PaperTrade]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "select * from cryptozavr.paper_trades"
                " order by opened_at_ms desc limit $1 offset $2",
                limit,
                offset,
            )
        return [_row_to_trade(r) for r in rows]

    async def count(self) -> int:
        async with self._pool.acquire() as conn:
            return await conn.fetchval("select count(*) from cryptozavr.paper_trades")

    async def stats(self) -> PaperStats:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("select * from cryptozavr.paper_stats")
        assert row is not None  # the view always returns a row
        return PaperStats(
            trades_count=row["trades_count"],
            wins=row["wins"],
            losses=row["losses"],
            open_count=row["open_count"],
            net_pnl_quote=row["net_pnl_quote"],
            avg_win_quote=row["avg_win_quote"],
            avg_loss_quote=row["avg_loss_quote"],
        )

    async def truncate(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("truncate cryptozavr.paper_trades")

def _row_to_trade(row: asyncpg.Record) -> PaperTrade:
    return PaperTrade(
        id=row["id"],
        side=PaperSide(row["side"]),
        venue=row["venue"],
        symbol_native=row["symbol_native"],
        entry=row["entry"],
        stop=row["stop"],
        take=row["take"],
        size_quote=row["size_quote"],
        opened_at_ms=row["opened_at_ms"],
        max_duration_sec=row["max_duration_sec"],
        status=PaperStatus(row["status"]),
        exit_price=row["exit_price"],
        closed_at_ms=row["closed_at_ms"],
        pnl_quote=row["pnl_quote"],
        reason=row["reason"],
        watch_id=row["watch_id"],
        note=row["note"],
    )
```

- [ ] **Step 3.4: Verify tests pass**

```bash
uv run pytest tests/contract/test_paper_trade_repo.py -v
```
Expected: all pass.

- [ ] **Step 3.5: Lint + mypy**

```bash
uv run ruff check src/cryptozavr/infrastructure/persistence/paper_trade_repo.py tests/contract/test_paper_trade_repo.py
uv run ruff format --check src/cryptozavr/infrastructure/persistence/paper_trade_repo.py tests/contract/test_paper_trade_repo.py
uv run mypy src/cryptozavr/infrastructure/persistence/paper_trade_repo.py
```

- [ ] **Step 3.6: Commit**

`/tmp/commit-msg.txt`:

```sql
feat(persistence): add PaperTradeRepository

asyncpg CRUD + atomic close (UPDATE WHERE status='running') + stats
view read. All mutations idempotent — double-close is a no-op.
```

```bash
git add src/cryptozavr/infrastructure/persistence/paper_trade_repo.py tests/contract/test_paper_trade_repo.py
git commit -F /tmp/commit-msg.txt && rm /tmp/commit-msg.txt
```

---

## Task 4: PositionWatcher on_terminal hook

**Files:**
- Modify: `src/cryptozavr/application/services/position_watcher.py`
- Modify: `tests/unit/application/services/test_position_watcher.py`

- [ ] **Step 4.1: Add failing test**

Append to `tests/unit/application/services/test_position_watcher.py`:

```python
async def test_on_terminal_callback_fires_on_stop_hit(btc_symbol) -> None:
    ticks = [(Decimal("100"), 1_000), (Decimal("95"), 1_100)]
    ws = FakeWsProvider(ticks, hold_open=False)
    registry: dict = {}
    watcher = PositionWatcher(ws_provider=ws, registry=registry)
    calls: list[tuple[str, str]] = []

    async def on_terminal(watch_id: str, event) -> None:
        calls.append((watch_id, event.type.value))

    watch_id = await watcher.start(
        symbol=btc_symbol,
        side=WatchSide.LONG,
        entry=Decimal("100"),
        stop=Decimal("95"),
        take=Decimal("110"),
        size_quote=None,
        max_duration_sec=3600,
        on_terminal=on_terminal,
    )
    state = registry[watch_id]
    assert state._task is not None
    await asyncio.wait_for(state._task, timeout=1.0)
    assert len(calls) == 1
    assert calls[0] == (watch_id, "stop_hit")

async def test_on_terminal_not_fired_on_manual_stop(btc_symbol) -> None:
    ws = FakeWsProvider([(Decimal("100"), 1_000)], hold_open=True)
    registry: dict = {}
    watcher = PositionWatcher(ws_provider=ws, registry=registry)
    calls: list[str] = []

    async def on_terminal(_watch_id, _event) -> None:
        calls.append("fired")

    watch_id = await watcher.start(
        symbol=btc_symbol,
        side=WatchSide.LONG,
        entry=Decimal("100"),
        stop=Decimal("95"),
        take=Decimal("110"),
        size_quote=None,
        max_duration_sec=3600,
        on_terminal=on_terminal,
    )
    await asyncio.sleep(0.05)
    await watcher.stop(watch_id)
    # Manual stop is *not* a terminal event — callback must NOT fire.
    assert calls == []
```

- [ ] **Step 4.2: Verify tests fail**

```bash
uv run pytest tests/unit/application/services/test_position_watcher.py::test_on_terminal_callback_fires_on_stop_hit -v
```
Expected: FAIL — `start()` does not accept `on_terminal`.

- [ ] **Step 4.3: Add the hook**

In `src/cryptozavr/application/services/position_watcher.py`, update the module-level imports:

```python
from collections.abc import Awaitable, Callable
```

Change `PositionWatcher.start` signature and body:

```python
    async def start(
        self,
        *,
        symbol: Symbol,
        side: WatchSide,
        entry: Decimal,
        stop: Decimal,
        take: Decimal,
        size_quote: Decimal | None,
        max_duration_sec: int,
        on_terminal: Callable[[str, WatchEvent], Awaitable[None]] | None = None,
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
        state.ensure_cond()
        self._registry[watch_id] = state
        state._task = asyncio.create_task(
            self._run(state, on_terminal), name=f"watch-{watch_id}"
        )
        return watch_id
```

Change `PositionWatcher._run` signature and body:

```python
    async def _run(
        self,
        state: WatchState,
        on_terminal: Callable[[str, WatchEvent], Awaitable[None]] | None,
    ) -> None:
        try:
            async for price, ts_ms in self._ws.watch_ticker(state.symbol.native_symbol):
                state.current_price = price
                state.last_tick_at_ms = ts_ms
                _update_pnl(state, price)

                events = EventDetector.detect(state, price=price, now_ms=ts_ms)
                for event in events:
                    state.append_event(event)
                    if event.type.is_terminal:
                        state.status = WatchStatus(event.type.value)
                        await state.notify_change()
                        if on_terminal is not None:
                            try:
                                await on_terminal(state.watch_id, event)
                            except Exception as exc:  # noqa: BLE001
                                _LOG.exception(
                                    "on_terminal callback failed: %s", exc
                                )
                        return
                    state._fired_non_terminal.add(event.type)
                if events:
                    await state.notify_change()
        except asyncio.CancelledError:
            if state.status is WatchStatus.RUNNING:
                state.status = WatchStatus.CANCELLED
            await state.notify_change()
            raise
        except Exception as exc:
            _LOG.exception("watch loop failed: %s", exc)
            state.status = WatchStatus.ERROR
            await state.notify_change()
```

Import `WatchEvent` is already in scope via the existing `from cryptozavr.domain.watch import ...`.

- [ ] **Step 4.4: Verify tests pass**

```bash
uv run pytest tests/unit/application/services/test_position_watcher.py tests/unit/application/services/test_event_detector.py tests/unit/mcp/tools/test_watch_tools.py -v
```
Expected: 21 pass (15 existing + 2 new + 4 wait_for_event).

Adjust count if the number of existing tests differs.

- [ ] **Step 4.5: Lint + mypy**

```bash
uv run ruff check src/cryptozavr/application/services/position_watcher.py
uv run ruff format --check src/cryptozavr/application/services/position_watcher.py
uv run mypy src/cryptozavr/application/services/position_watcher.py
```

- [ ] **Step 4.6: Commit**

`/tmp/commit-msg.txt`:

```bash
feat(watcher): add on_terminal callback hook

PositionWatcher.start() now accepts an async callback invoked once
when the loop transitions to stop_hit / take_hit / timeout. Manual
cancel and error paths do NOT fire the hook — paper ledger treats
those as explicit closes, not auto-closes.
```

```bash
git add src/cryptozavr/application/services/position_watcher.py tests/unit/application/services/test_position_watcher.py
git commit -F /tmp/commit-msg.txt && rm /tmp/commit-msg.txt
```

---

## Task 5: PaperLedgerService

**Files:**
- Create: `src/cryptozavr/application/services/paper_ledger_service.py`
- Test: `tests/unit/application/services/test_paper_ledger_service.py`

- [ ] **Step 5.1: Write tests with fakes**

```python
# tests/unit/application/services/test_paper_ledger_service.py
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from cryptozavr.application.services.paper_ledger_service import PaperLedgerService
from cryptozavr.application.services.position_watcher import PositionWatcher
from cryptozavr.application.services.symbol_resolver import SymbolResolver
from cryptozavr.domain.paper import PaperSide, PaperStatus, PaperTrade
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId

@pytest.fixture
def symbol_registry() -> SymbolRegistry:
    reg = SymbolRegistry()
    reg.get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )
    return reg

class FakeRepo:
    def __init__(self) -> None:
        self.rows: dict[UUID, PaperTrade] = {}

    async def insert(self, trade: PaperTrade) -> None:
        self.rows[trade.id] = trade

    async def set_watch_id(self, trade_id: str, watch_id: str | None) -> None:
        tid = UUID(trade_id)
        current = self.rows[tid]
        self.rows[tid] = PaperTrade(**{**current.__dict__, "watch_id": watch_id})

    async def close(
        self,
        *,
        trade_id: str,
        exit_price: Decimal,
        closed_at_ms: int,
        pnl_quote: Decimal,
        reason: str,
        target_status: PaperStatus = PaperStatus.CLOSED,
    ) -> int:
        tid = UUID(trade_id)
        current = self.rows[tid]
        if current.status is not PaperStatus.RUNNING:
            return 0
        self.rows[tid] = PaperTrade(**{**current.__dict__,
            "status": target_status,
            "exit_price": exit_price,
            "closed_at_ms": closed_at_ms,
            "pnl_quote": pnl_quote,
            "reason": reason,
        })
        return 1

    async def fetch_by_id(self, trade_id: str) -> PaperTrade | None:
        return self.rows.get(UUID(trade_id))

    async def fetch_open(self) -> list[PaperTrade]:
        return [t for t in self.rows.values() if t.status is PaperStatus.RUNNING]

    async def mark_abandoned(self, trade_id: str, reason: str) -> int:
        tid = UUID(trade_id)
        current = self.rows[tid]
        if current.status is not PaperStatus.RUNNING:
            return 0
        self.rows[tid] = PaperTrade(**{**current.__dict__,
            "status": PaperStatus.ABANDONED,
            "reason": reason,
        })
        return 1

class FakeWs:
    def __init__(self, ticks: list[tuple[Decimal, int]], hold_open: bool = True) -> None:
        self._ticks = ticks
        self._hold_open = hold_open

    async def watch_ticker(self, _native: str) -> AsyncIterator[tuple[Decimal, int]]:
        for tick in self._ticks:
            yield tick
        if self._hold_open:
            await asyncio.Event().wait()

async def test_open_trade_inserts_and_starts_watch(symbol_registry) -> None:
    repo = FakeRepo()
    ws = FakeWs([(Decimal("100"), 1_000)], hold_open=True)
    registry: dict = {}
    watcher = PositionWatcher(ws_provider=ws, registry=registry)
    resolver = SymbolResolver(symbol_registry)
    ledger = PaperLedgerService(
        repository=repo,
        watcher=watcher,
        resolver=resolver,
    )

    trade = await ledger.open_trade(
        venue="kucoin",
        symbol="BTC-USDT",
        side=PaperSide.LONG,
        entry=Decimal("100"),
        stop=Decimal("95"),
        take=Decimal("110"),
        size_quote=Decimal("1000"),
        max_duration_sec=3600,
    )
    assert trade.status is PaperStatus.RUNNING
    assert trade.watch_id is not None
    assert trade.watch_id in registry
    await watcher.stop(trade.watch_id)

async def test_on_terminal_closes_trade_with_pnl(symbol_registry) -> None:
    repo = FakeRepo()
    ws = FakeWs([(Decimal("95"), 2_000)], hold_open=False)  # stop_hit immediately
    registry: dict = {}
    watcher = PositionWatcher(ws_provider=ws, registry=registry)
    resolver = SymbolResolver(symbol_registry)
    ledger = PaperLedgerService(
        repository=repo,
        watcher=watcher,
        resolver=resolver,
    )

    trade = await ledger.open_trade(
        venue="kucoin",
        symbol="BTC-USDT",
        side=PaperSide.LONG,
        entry=Decimal("100"),
        stop=Decimal("95"),
        take=Decimal("110"),
        size_quote=Decimal("1000"),
        max_duration_sec=3600,
    )
    # wait for the watch task to finish
    state = registry[trade.watch_id]
    await asyncio.wait_for(state._task, timeout=1.0)
    # give the callback a tick to run through asyncio.create_task
    await asyncio.sleep(0.05)

    closed = await repo.fetch_by_id(str(trade.id))
    assert closed is not None
    assert closed.status is PaperStatus.CLOSED
    assert closed.reason == "stop_hit"
    # long: (95 - 100) * (1000 / 100) = -50
    assert closed.pnl_quote == Decimal("-50.00")

async def test_close_trade_is_idempotent(symbol_registry) -> None:
    repo = FakeRepo()
    ws = FakeWs([(Decimal("100"), 1_000)], hold_open=True)
    registry: dict = {}
    watcher = PositionWatcher(ws_provider=ws, registry=registry)
    resolver = SymbolResolver(symbol_registry)
    ledger = PaperLedgerService(repository=repo, watcher=watcher, resolver=resolver)

    trade = await ledger.open_trade(
        venue="kucoin",
        symbol="BTC-USDT",
        side=PaperSide.LONG,
        entry=Decimal("100"),
        stop=Decimal("95"),
        take=Decimal("110"),
        size_quote=Decimal("1000"),
        max_duration_sec=3600,
    )
    first = await ledger.close_trade(
        str(trade.id), exit_price=Decimal("105"), reason="manual_cancel"
    )
    assert first.status is PaperStatus.CLOSED
    second = await ledger.close_trade(
        str(trade.id), exit_price=Decimal("101"), reason="manual_cancel"
    )
    assert second.status is PaperStatus.CLOSED
    assert second.exit_price == Decimal("105")  # first close wins

async def test_resume_open_watches_restarts_watches(symbol_registry) -> None:
    # Pre-populate repo with an open trade. Watcher registry is empty.
    repo = FakeRepo()
    prior_id = uuid4()
    symbol = symbol_registry.get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )
    pre_trade = PaperTrade(
        id=prior_id,
        side=PaperSide.LONG,
        venue="kucoin",
        symbol_native="BTC-USDT",
        entry=Decimal("100"),
        stop=Decimal("95"),
        take=Decimal("110"),
        size_quote=Decimal("1000"),
        opened_at_ms=1_000,
        max_duration_sec=3600,
        status=PaperStatus.RUNNING,
        watch_id="stale-watch-id",
    )
    await repo.insert(pre_trade)

    ws = FakeWs([(Decimal("100"), 1_500)], hold_open=True)
    registry: dict = {}
    watcher = PositionWatcher(ws_provider=ws, registry=registry)
    resolver = SymbolResolver(symbol_registry)
    ledger = PaperLedgerService(repository=repo, watcher=watcher, resolver=resolver)

    resumed = await ledger.resume_open_watches()
    assert resumed == 1
    reloaded = await repo.fetch_by_id(str(prior_id))
    assert reloaded is not None
    assert reloaded.watch_id != "stale-watch-id"
    assert reloaded.watch_id in registry
    await watcher.stop(reloaded.watch_id)
```

- [ ] **Step 5.2: Verify failures**

```bash
uv run pytest tests/unit/application/services/test_paper_ledger_service.py -v
```
Expected: module missing.

- [ ] **Step 5.3: Implement service**

```python
# src/cryptozavr/application/services/paper_ledger_service.py
"""PaperLedgerService — orchestrates repository + watcher for paper trading."""

from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Protocol
from uuid import uuid4

from cryptozavr.application.services.position_watcher import PositionWatcher
from cryptozavr.application.services.symbol_resolver import SymbolResolver
from cryptozavr.domain.exceptions import DomainError, TradeNotFoundError
from cryptozavr.domain.paper import (
    PaperSide,
    PaperStatus,
    PaperTrade,
)
from cryptozavr.domain.watch import WatchEvent, WatchSide

_LOG = logging.getLogger(__name__)

class _RepoProto(Protocol):
    async def insert(self, trade: PaperTrade) -> None: ...
    async def set_watch_id(self, trade_id: str, watch_id: str | None) -> None: ...
    async def close(
        self,
        *,
        trade_id: str,
        exit_price: Decimal,
        closed_at_ms: int,
        pnl_quote: Decimal,
        reason: str,
        target_status: PaperStatus = PaperStatus.CLOSED,
    ) -> int: ...
    async def fetch_by_id(self, trade_id: str) -> PaperTrade | None: ...
    async def fetch_open(self) -> list[PaperTrade]: ...
    async def mark_abandoned(self, trade_id: str, reason: str) -> int: ...

class PaperLedgerService:
    def __init__(
        self,
        *,
        repository: _RepoProto,
        watcher: PositionWatcher,
        resolver: SymbolResolver,
    ) -> None:
        self._repo = repository
        self._watcher = watcher
        self._resolver = resolver

    async def open_trade(
        self,
        *,
        venue: str,
        symbol: str,
        side: PaperSide,
        entry: Decimal,
        stop: Decimal,
        take: Decimal,
        size_quote: Decimal,
        max_duration_sec: int,
        note: str | None = None,
    ) -> PaperTrade:
        resolved = self._resolver.resolve(user_input=symbol, venue=venue)
        trade = PaperTrade(
            id=uuid4(),
            side=side,
            venue=venue,
            symbol_native=resolved.native_symbol,
            entry=entry,
            stop=stop,
            take=take,
            size_quote=size_quote,
            opened_at_ms=int(time.time() * 1000),
            max_duration_sec=max_duration_sec,
            status=PaperStatus.RUNNING,
            note=note,
        )
        await self._repo.insert(trade)

        try:
            watch_id = await self._watcher.start(
                symbol=resolved,
                side=WatchSide(side.value),
                entry=entry,
                stop=stop,
                take=take,
                size_quote=size_quote,
                max_duration_sec=max_duration_sec,
                on_terminal=self._make_terminal_handler(str(trade.id)),
            )
        except DomainError:
            await self._repo.mark_abandoned(str(trade.id), reason="watch_start_failed")
            raise

        await self._repo.set_watch_id(str(trade.id), watch_id)
        fresh = await self._repo.fetch_by_id(str(trade.id))
        assert fresh is not None
        return fresh

    async def close_trade(
        self,
        trade_id: str,
        *,
        exit_price: Decimal,
        reason: str = "manual_cancel",
    ) -> PaperTrade:
        current = await self._repo.fetch_by_id(trade_id)
        if current is None:
            raise TradeNotFoundError(trade_id=trade_id)
        if current.status is not PaperStatus.RUNNING:
            return current  # idempotent

        if current.watch_id is not None:
            try:
                await self._watcher.stop(current.watch_id)
            except DomainError:
                pass  # watch may have already terminated

        pnl = current.compute_pnl(exit_price=exit_price)
        await self._repo.close(
            trade_id=trade_id,
            exit_price=exit_price,
            closed_at_ms=int(time.time() * 1000),
            pnl_quote=pnl,
            reason=reason,
        )
        fresh = await self._repo.fetch_by_id(trade_id)
        assert fresh is not None
        return fresh

    async def resume_open_watches(self) -> int:
        """Re-attach live watches for every status='running' row. Returns count."""
        open_trades = await self._repo.fetch_open()
        resumed = 0
        for trade in open_trades:
            try:
                resolved = self._resolver.resolve(
                    user_input=trade.symbol_native, venue=trade.venue
                )
                new_watch_id = await self._watcher.start(
                    symbol=resolved,
                    side=WatchSide(trade.side.value),
                    entry=trade.entry,
                    stop=trade.stop,
                    take=trade.take,
                    size_quote=trade.size_quote,
                    max_duration_sec=trade.max_duration_sec,
                    on_terminal=self._make_terminal_handler(str(trade.id)),
                )
            except Exception as exc:  # noqa: BLE001
                _LOG.warning(
                    "resume failed for trade %s: %s — marking abandoned",
                    trade.id,
                    exc,
                )
                await self._repo.mark_abandoned(
                    str(trade.id), reason=f"resume_failed: {exc}"
                )
                continue
            await self._repo.set_watch_id(str(trade.id), new_watch_id)
            resumed += 1
        return resumed

    def _make_terminal_handler(self, trade_id: str):
        async def handler(watch_id: str, event: WatchEvent) -> None:
            trade = await self._repo.fetch_by_id(trade_id)
            if trade is None or trade.status is not PaperStatus.RUNNING:
                return
            pnl = trade.compute_pnl(exit_price=event.price)
            await self._repo.close(
                trade_id=trade_id,
                exit_price=event.price,
                closed_at_ms=event.ts_ms,
                pnl_quote=pnl,
                reason=event.type.value,
            )

        return handler
```

- [ ] **Step 5.4: Verify tests pass**

```bash
uv run pytest tests/unit/application/services/test_paper_ledger_service.py -v
```
Expected: all pass.

- [ ] **Step 5.5: Lint + mypy**

```bash
uv run ruff check src/cryptozavr/application/services/paper_ledger_service.py
uv run ruff format --check src/cryptozavr/application/services/paper_ledger_service.py
uv run mypy src/cryptozavr/application/services/paper_ledger_service.py
```

- [ ] **Step 5.6: Commit**

`/tmp/commit-msg.txt`:

```bash
feat(application): add PaperLedgerService

Orchestrates PaperTradeRepository + PositionWatcher. open_trade does
INSERT + watcher.start + set_watch_id. Terminal events auto-close
via on_terminal callback. close_trade is idempotent. Resume on
startup re-attaches live watches for running rows.
```

```bash
git add src/cryptozavr/application/services/paper_ledger_service.py tests/unit/application/services/test_paper_ledger_service.py
git commit -F /tmp/commit-msg.txt && rm /tmp/commit-msg.txt
```

---

## Task 6: MCP DTOs

**Files:**
- Modify: `src/cryptozavr/mcp/dtos.py`

- [ ] **Step 6.1: Inspect the existing DTO style**

Read `src/cryptozavr/mcp/dtos.py` to confirm the existing `BaseModel` / `ConfigDict(frozen=True)` pattern, then append the paper DTOs below its existing classes.

- [ ] **Step 6.2: Add DTOs**

Append to `src/cryptozavr/mcp/dtos.py`:

```python
from cryptozavr.domain.paper import (
    PaperSide,
    PaperStats,
    PaperStatus,
    PaperTrade,
)

class PaperTradeDTO(BaseModel):
    id: str
    side: PaperSide
    venue: str
    symbol: str
    entry: Decimal
    stop: Decimal
    take: Decimal
    size_quote: Decimal
    opened_at_ms: int
    max_duration_sec: int
    status: PaperStatus
    exit_price: Decimal | None
    closed_at_ms: int | None
    pnl_quote: Decimal | None
    reason: str | None
    watch_id: str | None
    note: str | None

    @classmethod
    def from_domain(cls, trade: PaperTrade) -> PaperTradeDTO:
        return cls(
            id=str(trade.id),
            side=trade.side,
            venue=trade.venue,
            symbol=trade.symbol_native,
            entry=trade.entry,
            stop=trade.stop,
            take=trade.take,
            size_quote=trade.size_quote,
            opened_at_ms=trade.opened_at_ms,
            max_duration_sec=trade.max_duration_sec,
            status=trade.status,
            exit_price=trade.exit_price,
            closed_at_ms=trade.closed_at_ms,
            pnl_quote=trade.pnl_quote,
            reason=trade.reason,
            watch_id=trade.watch_id,
            note=trade.note,
        )

class PaperStatsDTO(BaseModel):
    trades_count: int
    wins: int
    losses: int
    open_count: int
    win_rate: Decimal
    net_pnl_quote: Decimal
    avg_win_quote: Decimal
    avg_loss_quote: Decimal
    bankroll_initial: Decimal
    bankroll_live: Decimal

    @classmethod
    def from_stats(
        cls,
        stats: PaperStats,
        *,
        bankroll_initial: Decimal,
    ) -> PaperStatsDTO:
        return cls(
            trades_count=stats.trades_count,
            wins=stats.wins,
            losses=stats.losses,
            open_count=stats.open_count,
            win_rate=stats.win_rate,
            net_pnl_quote=stats.net_pnl_quote,
            avg_win_quote=stats.avg_win_quote,
            avg_loss_quote=stats.avg_loss_quote,
            bankroll_initial=bankroll_initial,
            bankroll_live=(bankroll_initial + stats.net_pnl_quote).quantize(
                Decimal("0.01")
            ),
        )
```

- [ ] **Step 6.3: Smoke test**

```bash
uv run python -c "from cryptozavr.mcp.dtos import PaperTradeDTO, PaperStatsDTO; print('OK')"
```

- [ ] **Step 6.4: Lint + mypy**

```bash
uv run ruff check src/cryptozavr/mcp/dtos.py
uv run ruff format --check src/cryptozavr/mcp/dtos.py
uv run mypy src/cryptozavr/mcp/dtos.py
```

- [ ] **Step 6.5: Commit**

`/tmp/commit-msg.txt`:

```python
feat(mcp): add DTOs for paper trading

PaperTradeDTO + PaperStatsDTO. PaperStatsDTO computes bankroll_live
from bankroll_initial + net_pnl_quote at serialization time.
```

```bash
git add src/cryptozavr/mcp/dtos.py
git commit -F /tmp/commit-msg.txt && rm /tmp/commit-msg.txt
```

---

## Task 7: Settings + Lifespan wiring

**Files:**
- Modify: `src/cryptozavr/mcp/settings.py`
- Modify: `src/cryptozavr/mcp/lifespan_state.py`
- Modify: `src/cryptozavr/mcp/bootstrap.py`

- [ ] **Step 7.1: Add setting**

In `src/cryptozavr/mcp/settings.py`, add field:

```python
    paper_bankroll_initial: Decimal = Field(
        default=Decimal("10000"),
        description="Starting paper-trading bankroll in quote currency (USDT).",
    )
```

Ensure `from decimal import Decimal` and `from pydantic import Field` are already imported; add if missing.

- [ ] **Step 7.2: Add lifespan keys + getters**

In `src/cryptozavr/mcp/lifespan_state.py`:

1. Inside `_LifespanKeys`:
```python
    paper_repo: str = "paper_repo"
    paper_ledger: str = "paper_ledger"
    paper_bankroll_override: str = "paper_bankroll_override"
```

2. Inside `TYPE_CHECKING`:
```python
    from cryptozavr.application.services.paper_ledger_service import PaperLedgerService
    from cryptozavr.infrastructure.persistence.paper_trade_repo import (
        PaperTradeRepository,
    )
```

3. Getters:
```python
def get_paper_ledger(ctx: Any = _CTX) -> PaperLedgerService:
    return cast("PaperLedgerService", ctx.lifespan_context[LIFESPAN_KEYS.paper_ledger])

def get_paper_repo(ctx: Any = _CTX) -> PaperTradeRepository:
    return cast(
        "PaperTradeRepository", ctx.lifespan_context[LIFESPAN_KEYS.paper_repo]
    )

def get_paper_bankroll_override(ctx: Any = _CTX) -> dict[str, Any]:
    return cast(
        "dict[str, Any]",
        ctx.lifespan_context[LIFESPAN_KEYS.paper_bankroll_override],
    )
```

The `paper_bankroll_override` is a shared dict (`{"value": Decimal | None}`) so tools can mutate it in place.

- [ ] **Step 7.3: Bootstrap wiring**

In `src/cryptozavr/mcp/bootstrap.py`, near other infra imports:

```python
from cryptozavr.application.services.paper_ledger_service import PaperLedgerService
from cryptozavr.infrastructure.persistence.paper_trade_repo import (
    PaperTradeRepository,
)
```

After `risk_policy_repo = RiskPolicyRepository(pool=pg_pool)` (or wherever other repos are built), add:

```python
    paper_repo = PaperTradeRepository(pool=pg_pool)
    paper_ledger = PaperLedgerService(
        repository=paper_repo,
        watcher=position_watcher,
        resolver=symbol_resolver,
    )
    paper_bankroll_override: dict[str, "Decimal | None"] = {"value": None}
```

(Adjust variable names to match what the file actually uses for watcher / resolver.)

Add entries to the lifespan state dict:

```python
        LIFESPAN_KEYS.paper_repo: paper_repo,
        LIFESPAN_KEYS.paper_ledger: paper_ledger,
        LIFESPAN_KEYS.paper_bankroll_override: paper_bankroll_override,
```

Directly after the state dict is assembled but before `yield`, resume:

```python
    try:
        resumed = await paper_ledger.resume_open_watches()
        if resumed:
            _LOG.info("paper ledger: resumed %d open trade(s)", resumed)
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("paper ledger resume failed: %s", exc)
```

(Import `_LOG` exists in the file or create one if missing — match the existing pattern.)

- [ ] **Step 7.4: Smoke test**

```bash
uv run pytest tests/unit tests/contract -m "not integration" -q
```
Expected: all pass — no regressions.

- [ ] **Step 7.5: Commit**

`/tmp/commit-msg.txt`:

```text
feat(mcp): wire PaperTradeRepository + PaperLedgerService into lifespan

Adds paper_repo / paper_ledger / paper_bankroll_override keys and
calls resume_open_watches() at startup so running trades recover
their watches after MCP subprocess restart.
```

```bash
git add src/cryptozavr/mcp/settings.py src/cryptozavr/mcp/lifespan_state.py src/cryptozavr/mcp/bootstrap.py
git commit -F /tmp/commit-msg.txt && rm /tmp/commit-msg.txt
```

---

## Task 8: MCP tools (paper_open_trade, close_trade, cancel_trade, reset, set_bankroll)

**Files:**
- Create: `src/cryptozavr/mcp/tools/paper.py`
- Modify: `src/cryptozavr/mcp/server.py`
- Test: `tests/unit/mcp/tools/test_paper_tools.py`

- [ ] **Step 8.1: Write tests**

```python
# tests/unit/mcp/tools/test_paper_tools.py
from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal
from uuid import UUID

import pytest
from fastmcp import Client, FastMCP

from cryptozavr.application.services.paper_ledger_service import PaperLedgerService
from cryptozavr.application.services.position_watcher import PositionWatcher
from cryptozavr.application.services.symbol_resolver import SymbolResolver
from cryptozavr.domain.paper import PaperTrade
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.mcp.lifespan_state import LIFESPAN_KEYS
from cryptozavr.mcp.tools.paper import register_paper_tools

class _StubWs:
    async def watch_ticker(self, _native: str):
        import asyncio
        await asyncio.Event().wait()
        yield

class _FakeRepo:
    def __init__(self) -> None:
        self.rows: dict[UUID, PaperTrade] = {}

    async def insert(self, trade):
        self.rows[trade.id] = trade

    async def set_watch_id(self, trade_id, watch_id):
        tid = UUID(trade_id)
        current = self.rows[tid]
        self.rows[tid] = PaperTrade(**{**current.__dict__, "watch_id": watch_id})

    async def close(self, *, trade_id, exit_price, closed_at_ms, pnl_quote, reason, target_status=None):
        from cryptozavr.domain.paper import PaperStatus
        tid = UUID(trade_id)
        current = self.rows[tid]
        if current.status is not PaperStatus.RUNNING:
            return 0
        self.rows[tid] = PaperTrade(**{
            **current.__dict__,
            "status": PaperStatus.CLOSED,
            "exit_price": exit_price,
            "closed_at_ms": closed_at_ms,
            "pnl_quote": pnl_quote,
            "reason": reason,
        })
        return 1

    async def fetch_by_id(self, trade_id):
        return self.rows.get(UUID(trade_id))

    async def fetch_open(self):
        from cryptozavr.domain.paper import PaperStatus
        return [t for t in self.rows.values() if t.status is PaperStatus.RUNNING]

    async def fetch_page(self, limit=200, offset=0):
        return list(self.rows.values())[offset : offset + limit]

    async def count(self):
        return len(self.rows)

    async def mark_abandoned(self, trade_id, reason):
        from cryptozavr.domain.paper import PaperStatus
        tid = UUID(trade_id)
        current = self.rows[tid]
        self.rows[tid] = PaperTrade(**{**current.__dict__, "status": PaperStatus.ABANDONED, "reason": reason})
        return 1

    async def truncate(self):
        self.rows.clear()

    async def stats(self):
        from cryptozavr.domain.paper import PaperStats
        return PaperStats(
            trades_count=0, wins=0, losses=0, open_count=len(self.rows),
            net_pnl_quote=Decimal("0"),
            avg_win_quote=Decimal("0"),
            avg_loss_quote=Decimal("0"),
        )

@pytest.fixture
def mcp_server():
    reg = SymbolRegistry()
    reg.get(VenueId.KUCOIN, "BTC", "USDT", market_type=MarketType.SPOT, native_symbol="BTC-USDT")
    resolver = SymbolResolver(reg)
    watch_registry: dict = {}
    watcher = PositionWatcher(ws_provider=_StubWs(), registry=watch_registry)
    repo = _FakeRepo()
    ledger = PaperLedgerService(repository=repo, watcher=watcher, resolver=resolver)
    bankroll_override: dict = {"value": None}

    @asynccontextmanager
    async def lifespan(_server):
        yield {
            LIFESPAN_KEYS.paper_repo: repo,
            LIFESPAN_KEYS.paper_ledger: ledger,
            LIFESPAN_KEYS.paper_bankroll_override: bankroll_override,
        }

    mcp = FastMCP("test", lifespan=lifespan)
    register_paper_tools(mcp, bankroll_initial=Decimal("10000"))
    return mcp

async def test_open_trade_returns_dto(mcp_server) -> None:
    async with Client(mcp_server) as client:
        r = await client.call_tool(
            "paper_open_trade",
            {
                "venue": "kucoin",
                "symbol": "BTC-USDT",
                "side": "long",
                "entry": "100",
                "stop": "95",
                "take": "110",
                "size_quote": "1000",
                "max_duration_sec": 3600,
            },
        )
        assert r.structured_content["status"] == "running"
        assert r.structured_content["watch_id"]
        tid = r.structured_content["id"]
        await client.call_tool(
            "paper_close_trade",
            {"trade_id": tid, "exit_price": "101", "reason": "manual_cancel"},
        )

async def test_close_trade_idempotent(mcp_server) -> None:
    async with Client(mcp_server) as client:
        opened = await client.call_tool(
            "paper_open_trade",
            {
                "venue": "kucoin", "symbol": "BTC-USDT", "side": "long",
                "entry": "100", "stop": "95", "take": "110",
                "size_quote": "1000", "max_duration_sec": 3600,
            },
        )
        tid = opened.structured_content["id"]
        first = await client.call_tool(
            "paper_close_trade",
            {"trade_id": tid, "exit_price": "101", "reason": "manual_cancel"},
        )
        assert first.structured_content["status"] == "closed"
        second = await client.call_tool(
            "paper_close_trade",
            {"trade_id": tid, "exit_price": "105", "reason": "manual_cancel"},
        )
        assert second.structured_content["status"] == "closed"
        assert second.structured_content["exit_price"] == "101"

async def test_reset_requires_confirm(mcp_server) -> None:
    async with Client(mcp_server) as client:
        with pytest.raises(Exception, match="RESET"):
            await client.call_tool("paper_reset", {"confirm": "no"})

async def test_set_bankroll_updates_override(mcp_server) -> None:
    async with Client(mcp_server) as client:
        r = await client.call_tool("paper_set_bankroll", {"bankroll": "5000"})
        assert Decimal(r.structured_content["bankroll_initial"]) == Decimal("5000")
```

- [ ] **Step 8.2: Verify failures**

```bash
uv run pytest tests/unit/mcp/tools/test_paper_tools.py -v
```

- [ ] **Step 8.3: Implement tools**

```python
# src/cryptozavr/mcp/tools/paper.py
"""MCP tools for paper trading: open, close, cancel, reset, set_bankroll."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from fastmcp import Context, FastMCP
from fastmcp.dependencies import Depends
from pydantic import Field

from cryptozavr.application.services.paper_ledger_service import PaperLedgerService
from cryptozavr.domain.exceptions import DomainError, ValidationError
from cryptozavr.domain.paper import PaperSide
from cryptozavr.mcp.dtos import PaperStatsDTO, PaperTradeDTO
from cryptozavr.mcp.errors import domain_to_tool_error
from cryptozavr.mcp.lifespan_state import (
    get_paper_bankroll_override,
    get_paper_ledger,
    get_paper_repo,
)

_LEDGER: PaperLedgerService = Depends(get_paper_ledger)
_REPO = Depends(get_paper_repo)
_OVERRIDE = Depends(get_paper_bankroll_override)

def _effective_bankroll(initial: Decimal, override: dict[str, Any]) -> Decimal:
    value = override.get("value")
    return value if value is not None else initial

def register_paper_tools(mcp: FastMCP, *, bankroll_initial: Decimal) -> None:
    @mcp.tool(
        name="paper_open_trade",
        description=(
            "Open a paper trade. Persists to Supabase, starts a position watch "
            "automatically, returns the trade with assigned watch_id. A "
            "terminal event on the watch (stop_hit / take_hit / timeout) "
            "closes the trade atomically. Use check_watch / wait_for_event "
            "with the returned watch_id for live monitoring."
        ),
        tags={"paper", "position", "write"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def paper_open_trade(
        venue: Annotated[str, Field(description="Venue id (e.g. 'kucoin').")],
        symbol: Annotated[str, Field(description="Native symbol, e.g. BTC-USDT.")],
        side: Annotated[str, Field(description="'long' or 'short'.")],
        entry: Annotated[Decimal, Field(description="Entry price.")],
        stop: Annotated[Decimal, Field(description="Stop price.")],
        take: Annotated[Decimal, Field(description="Take profit price.")],
        size_quote: Annotated[Decimal, Field(description="Position size in quote currency (USDT).")],
        ctx: Context,
        max_duration_sec: Annotated[int, Field(ge=60, le=86_400)] = 3_600,
        note: Annotated[str | None, Field(description="Optional free-form note.")] = None,
        ledger: PaperLedgerService = _LEDGER,
    ) -> PaperTradeDTO:
        await ctx.info(f"paper_open_trade {venue}/{symbol} {side} size={size_quote}")
        try:
            trade = await ledger.open_trade(
                venue=venue,
                symbol=symbol,
                side=PaperSide(side),
                entry=entry,
                stop=stop,
                take=take,
                size_quote=size_quote,
                max_duration_sec=max_duration_sec,
                note=note,
            )
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc
        return PaperTradeDTO.from_domain(trade)

    @mcp.tool(
        name="paper_close_trade",
        description=(
            "Close an open paper trade at a given exit price. Idempotent — "
            "closing an already-closed trade returns its current snapshot."
        ),
        tags={"paper", "position"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def paper_close_trade(
        trade_id: Annotated[str, Field(description="Trade uuid.")],
        exit_price: Annotated[Decimal, Field(description="Exit price.")],
        ctx: Context,
        reason: Annotated[str, Field(description="Close reason.")] = "manual_cancel",
        ledger: PaperLedgerService = _LEDGER,
    ) -> PaperTradeDTO:
        await ctx.info(f"paper_close_trade {trade_id} @ {exit_price}")
        try:
            trade = await ledger.close_trade(
                trade_id, exit_price=exit_price, reason=reason
            )
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc
        return PaperTradeDTO.from_domain(trade)

    @mcp.tool(
        name="paper_cancel_trade",
        description=(
            "Alias for paper_close_trade with reason='manual_cancel'. "
            "Requires explicit exit_price (fetch a fresh ticker first)."
        ),
        tags={"paper", "position"},
    )
    async def paper_cancel_trade(
        trade_id: Annotated[str, Field(description="Trade uuid.")],
        exit_price: Annotated[Decimal, Field(description="Exit price.")],
        ctx: Context,
        ledger: PaperLedgerService = _LEDGER,
    ) -> PaperTradeDTO:
        await ctx.info(f"paper_cancel_trade {trade_id}")
        try:
            trade = await ledger.close_trade(
                trade_id, exit_price=exit_price, reason="manual_cancel"
            )
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc
        return PaperTradeDTO.from_domain(trade)

    @mcp.tool(
        name="paper_reset",
        description=(
            "Wipe the paper-trading ledger. Requires confirm='RESET'. Also "
            "clears the bankroll override."
        ),
        tags={"paper", "write", "dangerous"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
        },
    )
    async def paper_reset(
        confirm: Annotated[str, Field(description="Must equal 'RESET' to proceed.")],
        ctx: Context,
        repo = _REPO,
        override: dict[str, Any] = _OVERRIDE,
    ) -> dict[str, Any]:
        if confirm != "RESET":
            raise domain_to_tool_error(
                ValidationError("confirm must equal 'RESET'")
            )
        await ctx.warning("paper_reset TRUNCATE")
        before = await repo.count()
        await repo.truncate()
        override["value"] = None
        return {"trades_deleted": before, "bankroll_initial": str(bankroll_initial)}

    @mcp.tool(
        name="paper_set_bankroll",
        description=(
            "Override the bankroll used for live-bankroll calculations "
            "(bankroll_initial + net_pnl_quote). Does NOT touch persisted "
            "trades. Pass a positive Decimal."
        ),
        tags={"paper", "config"},
    )
    async def paper_set_bankroll(
        bankroll: Annotated[Decimal, Field(description="New bankroll (>0).")],
        ctx: Context,
        repo = _REPO,
        override: dict[str, Any] = _OVERRIDE,
    ) -> PaperStatsDTO:
        if bankroll <= 0:
            raise domain_to_tool_error(
                ValidationError("bankroll must be positive")
            )
        override["value"] = bankroll
        stats = await repo.stats()
        return PaperStatsDTO.from_stats(stats, bankroll_initial=bankroll)
```

- [ ] **Step 8.4: Register in server**

In `src/cryptozavr/mcp/server.py`:

1. Import:
```python
from cryptozavr.mcp.tools.paper import register_paper_tools
```

2. After the other `register_xxx(mcp)` calls:
```python
    register_paper_tools(mcp, bankroll_initial=settings.paper_bankroll_initial)
```

- [ ] **Step 8.5: Verify tests pass**

```bash
uv run pytest tests/unit/mcp/tools/test_paper_tools.py tests/unit tests/contract -m "not integration" -q
```

- [ ] **Step 8.6: Lint + mypy**

```bash
uv run ruff check src/cryptozavr/mcp/tools/paper.py tests/unit/mcp/tools/test_paper_tools.py src/cryptozavr/mcp/server.py
uv run ruff format --check src/cryptozavr/mcp/tools/paper.py tests/unit/mcp/tools/test_paper_tools.py src/cryptozavr/mcp/server.py
uv run mypy src/cryptozavr/mcp/tools/paper.py
```

- [ ] **Step 8.7: Commit**

`/tmp/commit-msg.txt`:

```bash
feat(mcp): add paper trading tools

paper_open_trade auto-starts a watch + registers on_terminal
callback. paper_close_trade is idempotent. paper_cancel_trade is
a thin alias. paper_reset requires confirm='RESET'. paper_set_bankroll
updates the in-memory override.
```

```bash
git add src/cryptozavr/mcp/tools/paper.py src/cryptozavr/mcp/server.py tests/unit/mcp/tools/test_paper_tools.py
git commit -F /tmp/commit-msg.txt && rm /tmp/commit-msg.txt
```

---

## Task 9: MCP resources

**Files:**
- Create: `src/cryptozavr/mcp/resources/paper.py`
- Modify: `src/cryptozavr/mcp/server.py`

- [ ] **Step 9.1: Inspect existing resource style**

Read `src/cryptozavr/mcp/resources/catalogs.py` for the `ResourceResult` + `ResourceContent(json.dumps(...))` pattern used everywhere in this project (per CLAUDE.md, URI-template resources require `ResourceResult` to preserve MIME type).

- [ ] **Step 9.2: Implement resources**

```python
# src/cryptozavr/mcp/resources/paper.py
"""MCP resources for paper trading: ledger, open_trades, stats, trades/{id}."""

from __future__ import annotations

import json
from decimal import Decimal

from fastmcp import FastMCP
from fastmcp.dependencies import Depends
from fastmcp.resources import ResourceContent, ResourceResult

from cryptozavr.domain.exceptions import TradeNotFoundError
from cryptozavr.infrastructure.persistence.paper_trade_repo import (
    PaperTradeRepository,
)
from cryptozavr.mcp.dtos import PaperStatsDTO, PaperTradeDTO
from cryptozavr.mcp.errors import domain_to_tool_error
from cryptozavr.mcp.lifespan_state import (
    get_paper_bankroll_override,
    get_paper_repo,
)

_REPO = Depends(get_paper_repo)
_OVERRIDE = Depends(get_paper_bankroll_override)

def register_paper_resources(mcp: FastMCP, *, bankroll_initial: Decimal) -> None:
    def _effective(override: dict) -> Decimal:
        value = override.get("value")
        return value if value is not None else bankroll_initial

    @mcp.resource(
        uri="cryptozavr://paper/ledger",
        name="paper_ledger",
        description="All paper trades, newest first (bounded 200).",
        mime_type="application/json",
    )
    async def ledger(repo: PaperTradeRepository = _REPO) -> ResourceResult:
        trades = await repo.fetch_page(limit=200, offset=0)
        total = await repo.count()
        payload = {
            "trades": [PaperTradeDTO.from_domain(t).model_dump(mode="json") for t in trades],
            "total_count": total,
            "returned": len(trades),
        }
        return ResourceResult(
            ResourceContent(content=json.dumps(payload), mime_type="application/json")
        )

    @mcp.resource(
        uri="cryptozavr://paper/open_trades",
        name="paper_open_trades",
        description="Only status='running' trades, newest first.",
        mime_type="application/json",
    )
    async def open_trades(repo: PaperTradeRepository = _REPO) -> ResourceResult:
        trades = await repo.fetch_open()
        payload = {
            "trades": [PaperTradeDTO.from_domain(t).model_dump(mode="json") for t in trades],
            "count": len(trades),
        }
        return ResourceResult(
            ResourceContent(content=json.dumps(payload), mime_type="application/json")
        )

    @mcp.resource(
        uri="cryptozavr://paper/stats",
        name="paper_stats",
        description="Aggregate paper-trading statistics + live bankroll.",
        mime_type="application/json",
    )
    async def stats(
        repo: PaperTradeRepository = _REPO,
        override: dict = _OVERRIDE,
    ) -> ResourceResult:
        s = await repo.stats()
        dto = PaperStatsDTO.from_stats(s, bankroll_initial=_effective(override))
        return ResourceResult(
            ResourceContent(
                content=json.dumps(dto.model_dump(mode="json")),
                mime_type="application/json",
            )
        )

    @mcp.resource(
        uri="cryptozavr://paper/trades/{trade_id}",
        name="paper_trade_detail",
        description="Full snapshot of a single paper trade by id.",
        mime_type="application/json",
    )
    async def trade_detail(
        trade_id: str, repo: PaperTradeRepository = _REPO
    ) -> ResourceResult:
        try:
            trade = await repo.fetch_by_id(trade_id)
        except Exception as exc:  # noqa: BLE001
            raise domain_to_tool_error(
                TradeNotFoundError(trade_id=trade_id)
            ) from exc
        if trade is None:
            raise domain_to_tool_error(TradeNotFoundError(trade_id=trade_id))
        dto = PaperTradeDTO.from_domain(trade)
        return ResourceResult(
            ResourceContent(
                content=json.dumps(dto.model_dump(mode="json")),
                mime_type="application/json",
            )
        )
```

- [ ] **Step 9.3: Register in server**

In `src/cryptozavr/mcp/server.py`:

```python
from cryptozavr.mcp.resources.paper import register_paper_resources
```

After other `register_*` calls:

```python
    register_paper_resources(mcp, bankroll_initial=settings.paper_bankroll_initial)
```

- [ ] **Step 9.4: Smoke test**

```bash
uv run python -c "
from cryptozavr.mcp.server import build_server
from cryptozavr.mcp.settings import Settings
s = Settings()
mcp = build_server(s)
print('OK, tools:', len(mcp.get_tools() if hasattr(mcp, 'get_tools') else []))
"
```

Expected: no errors (exact output depends on FastMCP version — the smoke-import is the test).

- [ ] **Step 9.5: Lint + mypy**

```bash
uv run ruff check src/cryptozavr/mcp/resources/paper.py src/cryptozavr/mcp/server.py
uv run ruff format --check src/cryptozavr/mcp/resources/paper.py src/cryptozavr/mcp/server.py
uv run mypy src/cryptozavr/mcp/resources/paper.py
```

- [ ] **Step 9.6: Commit**

`/tmp/commit-msg.txt`:

```text
feat(mcp): add paper trading resources

cryptozavr://paper/{ledger,open_trades,stats,trades/{id}} — all
read-only JSON views backed by PaperTradeRepository + paper_stats
view. Bankroll override from lifespan is honoured.
```

```bash
git add src/cryptozavr/mcp/resources/paper.py src/cryptozavr/mcp/server.py
git commit -F /tmp/commit-msg.txt && rm /tmp/commit-msg.txt
```

---

## Task 10: MCP prompts

**Files:**
- Create: `src/cryptozavr/mcp/prompts/paper.py`
- Modify: `src/cryptozavr/mcp/server.py`

- [ ] **Step 10.1: Inspect existing prompt style**

Read `src/cryptozavr/mcp/prompts/research.py` to match the `@mcp.prompt` patterns.

- [ ] **Step 10.2: Implement prompts**

```python
# src/cryptozavr/mcp/prompts/paper.py
"""MCP prompts for paper trading sessions and reviews."""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.prompts import Message

def register_paper_prompts(mcp: FastMCP) -> None:
    @mcp.prompt(
        name="paper_scalp_session",
        description=(
            "Start a disciplined paper-trading scalp session with session "
            "rules pinned up-front."
        ),
        tags={"paper", "session"},
    )
    def paper_scalp_session(
        max_trades: int = 20,
        max_duration_min: int = 60,
    ) -> list[Message]:
        system = (
            f"You are running a paper-trading scalp session with a strict rulebook:\n"
            f"1. Use cryptozavr://paper/stats for current bankroll.\n"
            f"2. Max {max_trades} trades, max {max_duration_min} minutes.\n"
            f"3. Risk per trade <= 2% of bankroll.\n"
            f"4. RR >= 1 always; prefer >= 1.5.\n"
            f"5. After 3 losses in a row — pause at least 10 minutes.\n"
            f"6. NEVER trade against a clear trend (check analyze_snapshot).\n"
            f"7. Use paper_open_trade. Monitor with wait_for_event on the "
            f"returned watch_id. Never bypass stops.\n"
            f"8. At session end, call the paper_review prompt."
        )
        user = "Begin. Call /cryptozavr:health, get_ticker, analyze_snapshot first."
        return [Message(system, role="assistant"), Message(user, role="user")]

    @mcp.prompt(
        name="paper_review",
        description=(
            "Review the most recent paper-trading session: reads ledger + "
            "stats, extracts patterns."
        ),
        tags={"paper", "review"},
    )
    def paper_review(last_n: int = 20) -> list[Message]:
        system = (
            f"Review my last {last_n} paper trades. Read cryptozavr://paper/ledger "
            f"and cryptozavr://paper/stats. Produce a short report:\n"
            f"- Bias: where were you biased (long vs short win rates, counter-trend "
            f"vs with-trend).\n"
            f"- Winning conditions: what made winners win (time of day, regime, "
            f"symbol, note content).\n"
            f"- Losing conditions: what made losers lose.\n"
            f"- Psychological notes: patterns in the 'note' field if present.\n"
            f"- One concrete rule to add to the next session."
        )
        return [Message(system, role="assistant")]

    @mcp.prompt(
        name="discretionary_watch_loop",
        description=(
            "The event-driven discretionary loop: wait_for_event → decide → "
            "act → repeat until terminal."
        ),
        tags={"paper", "runtime"},
    )
    def discretionary_watch_loop(trade_id: str) -> list[Message]:
        system = (
            f"You have an open paper trade {trade_id}. Enter the discretionary loop:\n"
            f"1. Call wait_for_event on the trade's watch_id (from paper_trades/{trade_id}).\n"
            f"2. On each event choose exactly one action:\n"
            f"   - 'move_stop_to_breakeven' (when breakeven_reached fires)\n"
            f"   - 'partial_close' via paper_close_trade of a fraction if you build one\n"
            f"   - 'close' via paper_close_trade if thesis is broken\n"
            f"   - 'hold' — no-op, keep looping.\n"
            f"3. On stop_hit / take_hit / timeout the trade auto-closes. Stop looping.\n"
            f"4. Log decisions in the note via paper_set_note (future tool) or via a "
            f"post-close note on the next open."
        )
        return [Message(system, role="assistant")]
```

- [ ] **Step 10.3: Register in server**

```python
from cryptozavr.mcp.prompts.paper import register_paper_prompts
```

```python
    register_paper_prompts(mcp)
```

- [ ] **Step 10.4: Smoke + lint + mypy**

```bash
uv run python -c "from cryptozavr.mcp.prompts.paper import register_paper_prompts; print('OK')"
uv run ruff check src/cryptozavr/mcp/prompts/paper.py src/cryptozavr/mcp/server.py
uv run ruff format --check src/cryptozavr/mcp/prompts/paper.py src/cryptozavr/mcp/server.py
uv run mypy src/cryptozavr/mcp/prompts/paper.py
```

- [ ] **Step 10.5: Commit**

`/tmp/commit-msg.txt`:

```text
feat(mcp): add paper trading prompts

paper_scalp_session pins a rulebook. paper_review reads ledger +
stats and produces a post-session report. discretionary_watch_loop
is the event-driven runtime cycle replacing the bash/sleep hacks.
```

```bash
git add src/cryptozavr/mcp/prompts/paper.py src/cryptozavr/mcp/server.py
git commit -F /tmp/commit-msg.txt && rm /tmp/commit-msg.txt
```

---

## Task 11: Integration test against live stack

**Files:**
- Create: `tests/integration/test_paper_ledger_live.py`

- [ ] **Step 11.1: Write the test**

```python
# tests/integration/test_paper_ledger_live.py
"""Live stack test: KuCoin WS + Supabase. Skipped by env flags."""

from __future__ import annotations

import asyncio
import os
from decimal import Decimal

import pytest

from cryptozavr.application.services.paper_ledger_service import PaperLedgerService
from cryptozavr.application.services.position_watcher import PositionWatcher
from cryptozavr.application.services.symbol_resolver import SymbolResolver
from cryptozavr.domain.paper import PaperSide, PaperStatus
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.persistence.paper_trade_repo import (
    PaperTradeRepository,
)
from cryptozavr.infrastructure.providers.kucoin_ws import KucoinWsProvider
from cryptozavr.infrastructure.supabase.pg_pool import PgPoolConfig, create_pool

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("SKIP_LIVE_TESTS") == "1"
        or os.getenv("SKIP_SUPABASE_TESTS") == "1"
        or not os.getenv("SUPABASE_DB_URL"),
        reason="live stack tests disabled",
    ),
]

async def test_open_and_manual_close_end_to_end() -> None:
    pool = await create_pool(PgPoolConfig(dsn=os.environ["SUPABASE_DB_URL"]))
    ws = KucoinWsProvider()
    try:
        await pool.execute("truncate cryptozavr.paper_trades")
        repo = PaperTradeRepository(pool=pool)
        reg = SymbolRegistry()
        reg.get(
            VenueId.KUCOIN,
            "BTC",
            "USDT",
            market_type=MarketType.SPOT,
            native_symbol="BTC-USDT",
        )
        resolver = SymbolResolver(reg)
        registry: dict = {}
        watcher = PositionWatcher(ws_provider=ws, registry=registry)
        ledger = PaperLedgerService(
            repository=repo, watcher=watcher, resolver=resolver
        )

        trade = await ledger.open_trade(
            venue="kucoin",
            symbol="BTC-USDT",
            side=PaperSide.LONG,
            entry=Decimal("1"),  # absurd so nothing hits
            stop=Decimal("0.5"),
            take=Decimal("1000000"),
            size_quote=Decimal("100"),
            max_duration_sec=120,
        )
        assert trade.status is PaperStatus.RUNNING

        # wait for at least one tick
        state = registry[trade.watch_id]
        for _ in range(50):
            if state.current_price is not None:
                break
            await asyncio.sleep(0.1)
        assert state.current_price is not None

        closed = await ledger.close_trade(
            str(trade.id),
            exit_price=state.current_price,
            reason="manual_cancel",
        )
        assert closed.status is PaperStatus.CLOSED
        assert closed.reason == "manual_cancel"
        await pool.execute(
            "delete from cryptozavr.paper_trades where id = $1", trade.id
        )
    finally:
        await ws.close()
        await pool.close()
```

- [ ] **Step 11.2: Run it**

```bash
uv run pytest tests/integration/test_paper_ledger_live.py -v
```
Expected: PASS within ~6s.

- [ ] **Step 11.3: Commit**

`/tmp/commit-msg.txt`:

```text
test(integration): add live paper ledger smoke test

Opens trade against KuCoin WS + Supabase, verifies a real tick is
received, closes manually, asserts final state. Gated by existing
SKIP_LIVE_TESTS and SKIP_SUPABASE_TESTS env flags.
```

```bash
git add tests/integration/test_paper_ledger_live.py
git commit -F /tmp/commit-msg.txt && rm /tmp/commit-msg.txt
```

---

## Task 12: Changelog + version bump + push

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `src/cryptozavr/__init__.py`
- Modify: `pyproject.toml`
- Modify: `.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`

- [ ] **Step 12.1: Update CHANGELOG**

Open `CHANGELOG.md`. Under `## [Unreleased]` (or the top section), add:

```markdown
### Added
- Paper trading ledger: `paper_open_trade`, `paper_close_trade`,
  `paper_cancel_trade`, `paper_reset`, `paper_set_bankroll` MCP tools.
- Paper trading resources: `cryptozavr://paper/ledger`,
  `/open_trades`, `/stats`, `/trades/{id}`.
- Paper trading prompts: `paper_scalp_session`, `paper_review`,
  `discretionary_watch_loop`.
- `PositionWatcher.start()` now accepts an `on_terminal` callback.
- Migration `00000000000090_paper_trades.sql` — table, view, realtime.
- Resume-on-startup: running paper trades re-attach live watches.
```

- [ ] **Step 12.2: Bump version**

```bash
sed -i '' 's/version = "0.3.5"/version = "0.4.0"/' pyproject.toml
sed -i '' 's/__version__ = "0.3.5"/__version__ = "0.4.0"/' src/cryptozavr/__init__.py
sed -i '' 's/"version": "0.3.5"/"version": "0.4.0"/' .claude-plugin/plugin.json .claude-plugin/marketplace.json
```

Verify:

```bash
grep -H "0.4.0" pyproject.toml src/cryptozavr/__init__.py .claude-plugin/plugin.json .claude-plugin/marketplace.json
```

- [ ] **Step 12.3: Final test + lint sweep**

```bash
uv run pytest tests/unit tests/contract -m "not integration" -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```
All must be green.

- [ ] **Step 12.4: Commit**

`/tmp/commit-msg.txt`:

```text
chore(release): 0.4.0 — paper trading ledger

Phase A of the scalping infrastructure roadmap: first-class paper
trading subsystem on Supabase, automated via PositionWatcher
on_terminal callback, with Realtime broadcast.
```

```bash
git add CHANGELOG.md src/cryptozavr/__init__.py pyproject.toml .claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -F /tmp/commit-msg.txt && rm /tmp/commit-msg.txt
```

- [ ] **Step 12.5: Push**

```bash
git push origin main
```

- [ ] **Step 12.6: Reinstall plugin in the operator's Claude Code**

Tell the operator (via the session reply):

```bash
Plugin 0.4.0 pushed. To load the new tools into an active session:
1. Exit: /exit
2. Reinstall in terminal:
     claude plugin marketplace update cryptozavr-marketplace
     claude plugin update cryptozavr@cryptozavr-marketplace
     pkill -f "cryptozavr.mcp.server"
3. Re-launch: claude --plugin-dir /Users/laptop/dev/cryptozavr
```
