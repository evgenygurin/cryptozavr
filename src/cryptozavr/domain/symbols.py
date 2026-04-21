"""Symbol entity + SymbolRegistry Flyweight factory."""

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
                raise ValidationError(f"Symbol.{attr} must be uppercase alphanumeric (got {val!r})")

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

    Thread-safe: internal dict is guarded by a lock. One registry per DI scope
    in production; tests use fresh registries per test.
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
                venue=venue,
                base=base,
                quote=quote,
                market_type=market_type,
                native_symbol=native_symbol,
            )
            self._store[key] = new_symbol
            return new_symbol

    def find(self, venue: VenueId, native_symbol: str) -> Symbol | None:
        """Look up a previously-registered Symbol by native_symbol on a venue."""
        with self._lock:
            for sym in self._store.values():
                if sym.venue == venue and sym.native_symbol == native_symbol:
                    return sym
        return None

    def find_by_base(
        self,
        venue: VenueId,
        base: str,
        *,
        quote: str,
        market_type: MarketType = MarketType.SPOT,
    ) -> Symbol | None:
        """Find Symbol by (venue, base, quote, market_type) identity."""
        key = (venue, base, quote, market_type)
        with self._lock:
            return self._store.get(key)
