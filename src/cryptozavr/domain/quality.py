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
