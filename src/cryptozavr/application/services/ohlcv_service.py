"""OhlcvService: orchestrates chain + factory + gateway for OHLCV fetches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cryptozavr.domain.exceptions import (
    SymbolNotFoundError,
    VenueNotSupportedError,
)
from cryptozavr.domain.market_data import OHLCVSeries
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Timeframe
from cryptozavr.domain.venues import VenueId
from cryptozavr.infrastructure.providers.chain.assembly import (
    build_ohlcv_chain,
)
from cryptozavr.infrastructure.providers.chain.context import (
    FetchContext,
    FetchOperation,
    FetchRequest,
)
from cryptozavr.infrastructure.providers.state.venue_state import VenueState


@dataclass(frozen=True, slots=True)
class OhlcvFetchResult:
    """OHLCV series + reason codes audit trail."""

    series: OHLCVSeries
    reason_codes: list[str]


class OhlcvService:
    """Facade: translates (venue, symbol, timeframe, limit) into a chain run."""

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

    async def fetch_ohlcv(
        self,
        *,
        venue: str,
        symbol: str,
        timeframe: Timeframe,
        limit: int = 500,
        since: Instant | None = None,
        force_refresh: bool = False,
    ) -> OhlcvFetchResult:
        venue_id = self._resolve_venue(venue)
        symbol_obj = self._registry.find(venue_id, symbol)
        if symbol_obj is None:
            raise SymbolNotFoundError(user_input=symbol, venue=venue)

        chain = build_ohlcv_chain(
            state=self._venue_states[venue_id],
            registry=self._registry,
            gateway=self._gateway,
            provider=self._providers[venue_id],
        )
        ctx = FetchContext(
            request=FetchRequest(
                operation=FetchOperation.OHLCV,
                symbol=symbol_obj,
                timeframe=timeframe,
                since=since,
                limit=limit,
                force_refresh=force_refresh,
            ),
        )
        result = await chain.handle(ctx)
        series: OHLCVSeries = result.metadata["result"]
        return OhlcvFetchResult(
            series=series,
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
