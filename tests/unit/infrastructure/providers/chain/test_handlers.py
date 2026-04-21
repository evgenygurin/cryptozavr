"""Test FetchHandler base + VenueHealthHandler."""

from __future__ import annotations

import pytest

from cryptozavr.domain.exceptions import ProviderUnavailableError
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId, VenueStateKind
from cryptozavr.infrastructure.providers.chain.context import (
    FetchContext,
    FetchOperation,
    FetchRequest,
)
from cryptozavr.infrastructure.providers.chain.handlers import (
    FetchHandler,
    VenueHealthHandler,
)
from cryptozavr.infrastructure.providers.state.venue_state import VenueState


@pytest.fixture
def btc_symbol():
    return SymbolRegistry().get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )


@pytest.fixture
def ctx(btc_symbol):
    return FetchContext(
        request=FetchRequest(
            operation=FetchOperation.TICKER,
            symbol=btc_symbol,
        ),
    )


class _PassthroughHandler(FetchHandler):
    async def handle(self, ctx: FetchContext) -> FetchContext:
        ctx.add_reason("passthrough")
        return await self._forward(ctx)


class TestFetchHandlerBase:
    @pytest.mark.asyncio
    async def test_terminal_handler_without_next(self, ctx) -> None:
        handler = _PassthroughHandler()
        result = await handler.handle(ctx)
        assert result is ctx
        assert ctx.reason_codes == ["passthrough"]

    @pytest.mark.asyncio
    async def test_set_next_chains_handlers(self, ctx) -> None:
        first = _PassthroughHandler()
        second = _PassthroughHandler()
        first.set_next(second)
        result = await first.handle(ctx)
        assert result is ctx
        assert ctx.reason_codes == ["passthrough", "passthrough"]


class TestVenueHealthHandler:
    @pytest.mark.asyncio
    async def test_healthy_forwards_with_reason(self, ctx) -> None:
        state = VenueState(VenueId.KUCOIN)
        handler = VenueHealthHandler(state)
        result = await handler.handle(ctx)
        assert result is ctx
        assert "venue:healthy" in ctx.reason_codes

    @pytest.mark.asyncio
    async def test_degraded_forwards_with_reason(self, ctx) -> None:
        state = VenueState(VenueId.KUCOIN, kind=VenueStateKind.DEGRADED)
        handler = VenueHealthHandler(state)
        result = await handler.handle(ctx)
        assert result is ctx
        assert "venue:degraded" in ctx.reason_codes

    @pytest.mark.asyncio
    async def test_down_raises(self, ctx) -> None:
        state = VenueState(VenueId.KUCOIN)
        state.mark_down()
        handler = VenueHealthHandler(state)
        with pytest.raises(ProviderUnavailableError):
            await handler.handle(ctx)
