"""Chain of Responsibility handlers for pre-fetch validation.

All handlers inherit FetchHandler base. Each either:
- mutates ctx (adds reason_code or metadata) and forwards to next
- short-circuits (returns ctx without forwarding, e.g. cache hit)
- raises a Domain exception (venue down, symbol not found)
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from cryptozavr.infrastructure.providers.chain.context import FetchContext
from cryptozavr.infrastructure.providers.state.venue_state import VenueState


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
