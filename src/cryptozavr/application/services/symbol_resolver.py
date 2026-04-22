"""SymbolResolver — fuzzy user-input → Symbol (in-memory MVP).

Algorithm (3-step cascade):
1. Resolve venue (string → VenueId, check it's known).
2. Normalise input: strip + upper.
3. Direct `registry.find(venue, native_symbol=normalised)`.
4. Format variants: strip separators, split on known quote suffix,
   reassemble with `-`, `/`, `""`.
5. Fall back to base-only lookup with default quotes (USDT, USD, BTC, ETH).
6. Raise SymbolNotFoundError if nothing matched.

pg_trgm DB-side fuzzy (Bitcoin → bitcoin aliases) deferred to M3.3+
when SupabaseGateway exposes alias queries.
"""

from cryptozavr.domain.exceptions import (
    SymbolNotFoundError,
    VenueNotSupportedError,
)
from cryptozavr.domain.symbols import Symbol, SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId

_DEFAULT_QUOTES: tuple[str, ...] = ("USDT", "USD", "BTC", "ETH")
_SEPARATORS: tuple[str, ...] = ("-", "/", "")


class SymbolResolver:
    """Translate any user input into a Symbol on a given venue."""

    def __init__(self, registry: SymbolRegistry) -> None:
        self._registry = registry

    def resolve(self, *, user_input: str, venue: str) -> Symbol:
        venue_id = self._resolve_venue(venue)
        normalised = user_input.strip().upper()

        # 1. Direct native_symbol hit.
        direct = self._registry.find(venue_id, normalised)
        if direct is not None:
            return direct

        # 2. Format variants (separator permutations, concatenated form).
        for candidate in self._variants(normalised):
            sym = self._registry.find(venue_id, candidate)
            if sym is not None:
                return sym

        # 3. Base-only → try common quotes.
        for quote in _DEFAULT_QUOTES:
            sym = self._registry.find_by_base(
                venue_id,
                normalised,
                quote=quote,
                market_type=MarketType.SPOT,
            )
            if sym is not None:
                return sym
            # "BTCUSDT" → base="BTC".
            if normalised.endswith(quote) and len(normalised) > len(quote):
                base = normalised[: -len(quote)]
                sym = self._registry.find_by_base(
                    venue_id,
                    base,
                    quote=quote,
                    market_type=MarketType.SPOT,
                )
                if sym is not None:
                    return sym

        # 4. Auto-register: if the input is parseable as BASE-QUOTE, register and return.
        parsed = self._parse_base_quote(normalised)
        if parsed is not None:
            base, quote = parsed
            native = f"{base}-{quote}"
            return self._registry.get(
                venue_id, base, quote, market_type=MarketType.SPOT, native_symbol=native
            )

        raise SymbolNotFoundError(user_input=user_input, venue=venue)

    @staticmethod
    def _resolve_venue(venue: str) -> VenueId:
        try:
            return VenueId(venue)
        except ValueError as exc:
            raise VenueNotSupportedError(venue=venue) from exc

    @staticmethod
    def _parse_base_quote(normalised: str) -> tuple[str, str] | None:
        """Return (base, quote) if normalised is a parseable BASE-QUOTE string."""
        for sep in ("-", "/"):
            if sep in normalised:
                base, _, quote = normalised.partition(sep)
                if base and quote:
                    return base, quote
        for quote in _DEFAULT_QUOTES:
            if normalised.endswith(quote) and len(normalised) > len(quote):
                return normalised[: -len(quote)], quote
        return None

    @staticmethod
    def _variants(normalised: str) -> list[str]:
        """Return plausible native_symbol forms for `normalised`."""
        out: set[str] = set()
        # Split on existing separators first.
        for sep in ("-", "/"):
            if sep in normalised:
                base, _, quote = normalised.partition(sep)
                for other in _SEPARATORS:
                    out.add(f"{base}{other}{quote}")
        # Try quote-suffix split (concatenated form).
        for quote in _DEFAULT_QUOTES:
            if normalised.endswith(quote) and len(normalised) > len(quote):
                base = normalised[: -len(quote)]
                for sep in _SEPARATORS:
                    out.add(f"{base}{sep}{quote}")
        out.discard(normalised)
        return sorted(out)
