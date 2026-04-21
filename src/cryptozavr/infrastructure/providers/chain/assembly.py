"""Chain assembly helpers. Wire handlers in the canonical order."""

from __future__ import annotations

from typing import Any

from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.infrastructure.providers.chain.handlers import (
    FetchHandler,
    ProviderFetchHandler,
    StalenessBypassHandler,
    SupabaseCacheHandler,
    SymbolExistsHandler,
    VenueHealthHandler,
)
from cryptozavr.infrastructure.providers.state.venue_state import VenueState


def build_ticker_chain(
    *,
    state: VenueState,
    registry: SymbolRegistry,
    gateway: Any,
    provider: Any,
) -> FetchHandler:
    """5-handler chain for ticker fetches."""
    return _build_chain(
        state=state,
        registry=registry,
        gateway=gateway,
        provider=provider,
    )


def build_ohlcv_chain(
    *,
    state: VenueState,
    registry: SymbolRegistry,
    gateway: Any,
    provider: Any,
) -> FetchHandler:
    """5-handler chain for OHLCV fetches (same topology; SupabaseCacheHandler
    dispatches to load_ohlcv based on request.operation)."""
    return _build_chain(
        state=state,
        registry=registry,
        gateway=gateway,
        provider=provider,
    )


def _build_chain(
    *,
    state: VenueState,
    registry: SymbolRegistry,
    gateway: Any,
    provider: Any,
) -> FetchHandler:
    head = VenueHealthHandler(state)
    head.set_next(SymbolExistsHandler(registry)).set_next(StalenessBypassHandler()).set_next(
        SupabaseCacheHandler(gateway)
    ).set_next(ProviderFetchHandler(provider=provider, gateway=gateway))
    return head
