"""Watch types: enums, frozen events, and mutable state."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from cryptozavr.domain.exceptions import ValidationError

if TYPE_CHECKING:
    from cryptozavr.domain.symbols import Symbol


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


_MIN_DURATION_SEC = 60
_MAX_DURATION_SEC = 86_400
_EVENT_BUFFER_CAP = 200


@dataclass(slots=True)
class WatchState:
    watch_id: str
    symbol: Symbol
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
                f"max_duration_sec must be in [{_MIN_DURATION_SEC}, {_MAX_DURATION_SEC}]"
            )

    def append_event(self, event: WatchEvent) -> None:
        self.events.append(event)
        if len(self.events) > _EVENT_BUFFER_CAP:
            del self.events[: len(self.events) - _EVENT_BUFFER_CAP]
