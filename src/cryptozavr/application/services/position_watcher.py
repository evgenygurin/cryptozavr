"""Position watcher service: EventDetector (pure) + PositionWatcher (stateful).

This file will grow in Task 5 to include PositionWatcher. For now only
EventDetector is exported.
"""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.domain.watch import EventType, WatchEvent, WatchSide, WatchState

_APPROACH_BAND_PCT = Decimal("0.005")  # 0.5%


class EventDetector:
    """Pure detector: (state, price, now_ms) -> list[WatchEvent].

    Terminal events (stop/take/timeout) are returned as a single-element
    list and take priority. Non-terminal events are deduplicated against
    state._fired_non_terminal — callers are responsible for updating
    that set.
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
            state.side, price, state.stop
        ):
            events.append(WatchEvent(EventType.PRICE_APPROACHES_STOP, now_ms, price, {}))
        if EventType.PRICE_APPROACHES_TAKE not in state._fired_non_terminal and _is_near_take(
            state.side, price, state.take
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
