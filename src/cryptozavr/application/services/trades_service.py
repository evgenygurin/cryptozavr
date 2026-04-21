"""TradesService: orchestrates chain + provider for recent-trades fetches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cryptozavr.domain.exceptions import (
    SymbolNotFoundError,
    VenueNotSupportedError,
)
from cryptozavr.domain.market_data import TradeTick
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant
from cryptozavr.domain.venues import VenueId
from cryptozavr.infrastructure.providers.chain.assembly import (
    build_trades_chain,
)
from cryptozavr.infrastructure.providers.chain.context import (
    FetchContext,
    FetchOperation,
    FetchRequest,
)
from cryptozavr.infrastructure.providers.state.venue_state import VenueState


@dataclass(frozen=True, slots=True)
class TradesFetchResult:
    """Recent trades + venue/symbol identifiers + reason codes audit trail.

    Venue/symbol are carried on the result (unlike Ticker/OHLCV where the
    domain object embeds Symbol) because TradeTick is per-trade and the
    collection-level (venue, symbol) context is orthogonal.
    """

    venue: str
    symbol: str
    trades: tuple[TradeTick, ...]
    reason_codes: list[str]


class TradesService:
    """Facade: translates (venue, symbol, limit, since) into a chain run."""

    def __init__(
        self,
        *,
        registry: SymbolRegistry,
        venue_states: dict[VenueId, VenueState],
        providers: dict[VenueId, Any],
        gateway: Any,
    ) -> None:
        self._registry = registry
        self._venue_states = venue_states
        self._providers = providers
        self._gateway = gateway

    async def fetch_trades(
        self,
        *,
        venue: str,
        symbol: str,
        limit: int = 100,
        since: Instant | None = None,
        force_refresh: bool = False,
    ) -> TradesFetchResult:
        venue_id = self._resolve_venue(venue)
        symbol_obj = self._registry.find(venue_id, symbol)
        if symbol_obj is None:
            raise SymbolNotFoundError(user_input=symbol, venue=venue)

        chain = build_trades_chain(
            state=self._venue_states[venue_id],
            registry=self._registry,
            gateway=self._gateway,
            provider=self._providers[venue_id],
        )
        ctx = FetchContext(
            request=FetchRequest(
                operation=FetchOperation.TRADES,
                symbol=symbol_obj,
                since=since,
                limit=limit,
                force_refresh=force_refresh,
            ),
        )
        result = await chain.handle(ctx)
        trades: tuple[TradeTick, ...] = tuple(result.metadata["result"])
        return TradesFetchResult(
            venue=venue,
            symbol=symbol,
            trades=trades,
            reason_codes=list(result.reason_codes),
        )

    def _resolve_venue(self, venue: str) -> VenueId:
        try:
            venue_id = VenueId(venue)
        except ValueError as exc:
            raise VenueNotSupportedError(venue=venue) from exc
        if venue_id not in self._venue_states:
            raise VenueNotSupportedError(venue=venue)
        return venue_id
