"""Position watcher service: EventDetector (pure) + PositionWatcher (stateful)."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol

from cryptozavr.domain.exceptions import WatchNotFoundError
from cryptozavr.domain.watch import EventType, WatchEvent, WatchSide, WatchState, WatchStatus

if TYPE_CHECKING:
    from cryptozavr.domain.symbols import Symbol

_APPROACH_BAND_RATIO = Decimal("0.2")  # 20% of entry↔level distance


class EventDetector:
    """Pure detector: (state, price, now_ms) -> list[WatchEvent].

    Terminal events (stop/take/timeout) are returned as a single-element
    list and take priority. Non-terminal events are deduplicated against
    state._fired_non_terminal — callers are responsible for updating
    that set.

    Approach bands scale with entry↔level distance (20%), not with the
    level price — so on a tight stop the band stays narrow and the
    approach event only fires when the price really closes in.
    """

    @staticmethod
    def detect(state: WatchState, *, price: Decimal, now_ms: int) -> list[WatchEvent]:
        if _is_stop_hit(state.side, price, state.stop):
            return [WatchEvent(EventType.STOP_HIT, now_ms, price, {})]
        if _is_take_hit(state.side, price, state.take):
            return [WatchEvent(EventType.TAKE_HIT, now_ms, price, {})]
        deadline_ms = state.started_at_ms + state.max_duration_sec * 1000
        if now_ms >= deadline_ms:
            return [WatchEvent(EventType.TIMEOUT, now_ms, price, {})]

        events: list[WatchEvent] = []
        if EventType.PRICE_APPROACHES_STOP not in state._fired_non_terminal and _is_near_stop(
            state, price
        ):
            events.append(WatchEvent(EventType.PRICE_APPROACHES_STOP, now_ms, price, {}))
        if EventType.PRICE_APPROACHES_TAKE not in state._fired_non_terminal and _is_near_take(
            state, price
        ):
            events.append(WatchEvent(EventType.PRICE_APPROACHES_TAKE, now_ms, price, {}))
        if EventType.BREAKEVEN_REACHED not in state._fired_non_terminal and _is_breakeven(
            state, price
        ):
            events.append(WatchEvent(EventType.BREAKEVEN_REACHED, now_ms, price, {}))
        return events


def _is_stop_hit(side: WatchSide, price: Decimal, stop: Decimal) -> bool:
    if side is WatchSide.LONG:
        return price <= stop
    return price >= stop


def _is_take_hit(side: WatchSide, price: Decimal, take: Decimal) -> bool:
    if side is WatchSide.LONG:
        return price >= take
    return price <= take


def _is_near_stop(state: WatchState, price: Decimal) -> bool:
    band = (state.entry - state.stop).copy_abs() * _APPROACH_BAND_RATIO
    if state.side is WatchSide.LONG:
        return state.stop < price <= state.stop + band
    return state.stop - band <= price < state.stop


def _is_near_take(state: WatchState, price: Decimal) -> bool:
    band = (state.take - state.entry).copy_abs() * _APPROACH_BAND_RATIO
    if state.side is WatchSide.LONG:
        return state.take - band <= price < state.take
    return state.take < price <= state.take + band


def _is_breakeven(state: WatchState, price: Decimal) -> bool:
    r = (state.entry - state.stop).copy_abs()
    if state.side is WatchSide.LONG:
        return price - state.entry >= r
    return state.entry - price >= r


_LOG = logging.getLogger(__name__)


class WsProviderProto(Protocol):
    def watch_ticker(self, native_symbol: str) -> AsyncIterator[tuple[Decimal, int]]: ...


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
        entry: Decimal,
        stop: Decimal,
        take: Decimal,
        size_quote: Decimal | None,
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
        state.ensure_cond()  # init change condition in event loop
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
            with contextlib.suppress(asyncio.CancelledError):
                await task
        if state.status is WatchStatus.RUNNING:
            state.status = WatchStatus.CANCELLED
        await state.notify_change()
        return state

    async def _run(self, state: WatchState) -> None:
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


def _update_pnl(state: WatchState, price: Decimal) -> None:
    if state.side is WatchSide.LONG:
        pct = (price - state.entry) / state.entry
    else:
        pct = (state.entry - price) / state.entry
    state.pnl_pct = pct.quantize(Decimal("0.0001"))
    if state.size_quote is not None:
        state.pnl_quote = (state.size_quote * pct).quantize(Decimal("0.01"))
