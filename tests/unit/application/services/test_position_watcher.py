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
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )


class FakeWsProvider:
    """Yields a scripted sequence of (price, ts_ms) tuples then blocks."""

    def __init__(
        self,
        ticks: list[tuple[Decimal, int]],
        hold_open: bool = True,
    ) -> None:
        self._ticks = ticks
        self._hold_open = hold_open

    async def watch_ticker(self, native_symbol: str) -> AsyncIterator[tuple[Decimal, int]]:
        for tick in self._ticks:
            yield tick
        if self._hold_open:
            await asyncio.Event().wait()

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
    await asyncio.sleep(0.05)
    await watcher.stop(watch_id)


async def test_stop_hit_terminates_loop(btc_symbol) -> None:
    ticks = [(Decimal("100"), 1_000), (Decimal("95"), 1_100)]
    ws = FakeWsProvider(ticks, hold_open=False)
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
        symbol=btc_symbol,
        side=WatchSide.LONG,
        entry=Decimal("100"),
        stop=Decimal("95"),
        take=Decimal("110"),
        size_quote=None,
        max_duration_sec=3600,
    )
    await asyncio.sleep(0.05)
    state = await watcher.stop(watch_id)
    assert state.status is WatchStatus.CANCELLED


async def test_check_returns_snapshot(btc_symbol) -> None:
    ws = FakeWsProvider([(Decimal("100"), 1_000)], hold_open=True)
    registry: dict = {}
    watcher = PositionWatcher(ws_provider=ws, registry=registry)

    watch_id = await watcher.start(
        symbol=btc_symbol,
        side=WatchSide.LONG,
        entry=Decimal("100"),
        stop=Decimal("95"),
        take=Decimal("110"),
        size_quote=Decimal("1000"),
        max_duration_sec=3600,
    )
    await asyncio.sleep(0.05)
    state = watcher.check(watch_id)
    assert state.current_price == Decimal("100")
    await watcher.stop(watch_id)
