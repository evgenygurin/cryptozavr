"""Chain of Responsibility handlers for pre-fetch validation.

All handlers inherit FetchHandler base. Each either:
- mutates ctx (adds reason_code or metadata) and forwards to next
- short-circuits (returns ctx without forwarding, e.g. cache hit)
- raises a Domain exception (venue down, symbol not found)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from cryptozavr.domain.exceptions import SymbolNotFoundError
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.infrastructure.providers.chain.context import FetchContext
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

_LOG = logging.getLogger(__name__)


class FetchHandler(ABC):
    """Base class for Chain of Responsibility handlers."""

    _next: FetchHandler | None = None

    def set_next(self, handler: FetchHandler) -> FetchHandler:
        """Link next handler; returns it for fluent chaining."""
        self._next = handler
        return handler

    @abstractmethod
    async def handle(self, ctx: FetchContext) -> FetchContext: ...

    async def _forward(self, ctx: FetchContext) -> FetchContext:
        """Delegate to next handler; terminal if no next."""
        if self._next is None:
            return ctx
        return await self._next.handle(ctx)


class VenueHealthHandler(FetchHandler):
    """First gate: checks VenueState.require_operational()."""

    def __init__(self, state: VenueState) -> None:
        self._state = state

    async def handle(self, ctx: FetchContext) -> FetchContext:
        self._state.require_operational()
        ctx.add_reason(f"venue:{self._state.kind.value}")
        return await self._forward(ctx)


class SymbolExistsHandler(FetchHandler):
    """Second gate: verifies the symbol is known to SymbolRegistry."""

    def __init__(self, registry: SymbolRegistry) -> None:
        self._registry = registry

    async def handle(self, ctx: FetchContext) -> FetchContext:
        symbol = ctx.request.symbol
        found = self._registry.find(symbol.venue, symbol.native_symbol)
        if found is None:
            raise SymbolNotFoundError(
                user_input=symbol.native_symbol,
                venue=symbol.venue.value,
            )
        ctx.add_reason("symbol:found")
        return await self._forward(ctx)


class StalenessBypassHandler(FetchHandler):
    """Reads request.force_refresh; marks metadata so cache handler skips."""

    async def handle(self, ctx: FetchContext) -> FetchContext:
        if ctx.request.force_refresh:
            ctx.metadata["bypass_cache"] = True
            ctx.add_reason("cache:bypassed")
        return await self._forward(ctx)


class SupabaseCacheHandler(FetchHandler):
    """Try to short-circuit the chain via Supabase-cached result.

    Respects metadata["bypass_cache"] set by StalenessBypassHandler.
    Gateway errors are caught and logged — they don't break the chain.
    """

    def __init__(self, gateway: Any) -> None:
        self._gateway = gateway

    async def handle(self, ctx: FetchContext) -> FetchContext:
        if ctx.metadata.get("bypass_cache"):
            return await self._forward(ctx)

        try:
            cached = await self._lookup(ctx)
        except Exception as exc:
            _LOG.warning("supabase cache lookup failed: %s", exc)
            ctx.add_reason("cache:error")
            return await self._forward(ctx)

        if cached is not None:
            ctx.metadata["result"] = cached
            ctx.add_reason("cache:hit")
            return ctx

        ctx.add_reason("cache:miss")
        return await self._forward(ctx)

    async def _lookup(self, ctx: FetchContext) -> Any:
        req = ctx.request
        if req.operation.value == "ticker":
            return await self._gateway.load_ticker(req.symbol)
        if req.operation.value == "ohlcv":
            return await self._gateway.load_ohlcv(
                req.symbol, req.timeframe, since=req.since, limit=req.limit
            )
        # order_book / trades not cached in M2.2 — always miss
        return None
