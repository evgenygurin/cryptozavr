"""Domain value objects: immutable, hashable, zero-I/O."""

from __future__ import annotations

from datetime import UTC, datetime
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
            raise ValidationError("Instant requires a timezone-aware datetime (UTC expected)")
        self._dt = dt.astimezone(UTC)

    @classmethod
    def from_ms(cls, ms: int) -> Instant:
        """Construct from Unix milliseconds (UTC)."""
        return cls(datetime.fromtimestamp(ms / 1000, tz=UTC))

    @classmethod
    def from_iso(cls, iso: str) -> Instant:
        """Parse ISO-8601. Accepts both '+00:00' and 'Z' suffix."""
        return cls(datetime.fromisoformat(iso.replace("Z", "+00:00")))

    @classmethod
    def now(cls) -> Instant:
        return cls(datetime.now(tz=UTC))

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
