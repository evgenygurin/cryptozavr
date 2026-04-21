"""Test FetchHandler base + VenueHealthHandler."""

from __future__ import annotations

import pytest

from cryptozavr.domain.exceptions import ProviderUnavailableError, SymbolNotFoundError
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId, VenueStateKind
from cryptozavr.infrastructure.providers.chain.context import (
    FetchContext,
    FetchOperation,
    FetchRequest,
)
from cryptozavr.infrastructure.providers.chain.handlers import (
    FetchHandler,
    StalenessBypassHandler,
    SymbolExistsHandler,
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


class TestSymbolExistsHandler:
    @pytest.mark.asyncio
    async def test_registered_symbol_forwards(self, ctx, btc_symbol) -> None:
        registry = SymbolRegistry()
        # Register the symbol so find() succeeds
        registry.get(
            VenueId.KUCOIN,
            "BTC",
            "USDT",
            market_type=MarketType.SPOT,
            native_symbol="BTC-USDT",
        )
        handler = SymbolExistsHandler(registry)
        result = await handler.handle(ctx)
        assert result is ctx
        assert "symbol:found" in ctx.reason_codes

    @pytest.mark.asyncio
    async def test_unregistered_symbol_raises(self, ctx) -> None:
        registry = SymbolRegistry()  # empty
        handler = SymbolExistsHandler(registry)
        with pytest.raises(SymbolNotFoundError):
            await handler.handle(ctx)


class TestStalenessBypassHandler:
    @pytest.mark.asyncio
    async def test_no_bypass_forwards(self, ctx) -> None:
        handler = StalenessBypassHandler()
        result = await handler.handle(ctx)
        assert result is ctx
        assert "cache:bypassed" not in ctx.reason_codes

    @pytest.mark.asyncio
    async def test_force_refresh_adds_bypass_reason(self, btc_symbol) -> None:
        req = FetchRequest(
            operation=FetchOperation.TICKER,
            symbol=btc_symbol,
            force_refresh=True,
        )
        ctx = FetchContext(request=req)
        handler = StalenessBypassHandler()
        result = await handler.handle(ctx)
        assert result is ctx
        assert "cache:bypassed" in ctx.reason_codes
        assert ctx.metadata.get("bypass_cache") is True
