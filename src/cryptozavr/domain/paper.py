"""Paper trading domain types.

PaperTrade is immutable (frozen). Mutations are represented as NEW
instances returned from repository operations; the DB is the source
of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
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
        delta = exit_price - self.entry if self.side is PaperSide.LONG else self.entry - exit_price
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
        return (Decimal(self.wins) / Decimal(self.trades_count)).quantize(Decimal("0.0001"))
