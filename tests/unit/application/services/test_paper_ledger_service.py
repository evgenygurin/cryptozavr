from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import replace
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
        self.rows[tid] = replace(current, watch_id=watch_id)

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
        self.rows[tid] = replace(
            current,
            status=target_status,
            exit_price=exit_price,
            closed_at_ms=closed_at_ms,
            pnl_quote=pnl_quote,
            reason=reason,
        )
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
        self.rows[tid] = replace(current, status=PaperStatus.ABANDONED, reason=reason)
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


async def test_open_trade_inserts_and_starts_watch(symbol_registry: SymbolRegistry) -> None:
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


async def test_on_terminal_closes_trade_with_pnl(symbol_registry: SymbolRegistry) -> None:
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
    state = registry[trade.watch_id]
    await asyncio.wait_for(state._task, timeout=1.0)
    await asyncio.sleep(0.05)

    closed = await repo.fetch_by_id(str(trade.id))
    assert closed is not None
    assert closed.status is PaperStatus.CLOSED
    assert closed.reason == "stop_hit"
    assert closed.pnl_quote == Decimal("-50.00")


async def test_close_trade_is_idempotent(symbol_registry: SymbolRegistry) -> None:
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


async def test_resume_open_watches_restarts_watches(symbol_registry: SymbolRegistry) -> None:
    repo = FakeRepo()
    prior_id = uuid4()
    symbol_registry.get(
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
