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


def build_order_book_chain(
    *,
    state: VenueState,
    registry: SymbolRegistry,
    gateway: Any,
    provider: Any,
) -> FetchHandler:
    """5-handler chain for order-book fetches.

    Same topology as ticker/ohlcv; order-book is not cached in M2.2 — the
    SupabaseCacheHandler returns None for this operation and the chain
    always reaches ProviderFetchHandler.
    """
    return _build_chain(
        state=state,
        registry=registry,
        gateway=gateway,
        provider=provider,
    )


def build_trades_chain(
    *,
    state: VenueState,
    registry: SymbolRegistry,
    gateway: Any,
    provider: Any,
) -> FetchHandler:
    """5-handler chain for trades fetches.

    Trades are not cached in M2.2 — same non-caching behaviour as
    order-book.
    """
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
