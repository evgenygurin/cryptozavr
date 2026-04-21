"""Test FetchHandler base + VenueHealthHandler."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from cryptozavr.domain.exceptions import ProviderUnavailableError, SymbolNotFoundError
from cryptozavr.domain.market_data import Ticker
from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Timeframe
from cryptozavr.domain.venues import MarketType, VenueId, VenueStateKind
from cryptozavr.infrastructure.providers.chain.context import (
    FetchContext,
    FetchOperation,
    FetchRequest,
)
from cryptozavr.infrastructure.providers.chain.handlers import (
    FetchHandler,
    ProviderFetchHandler,
    StalenessBypassHandler,
    SupabaseCacheHandler,
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


def _make_cached_ticker(symbol) -> Ticker:
    return Ticker(
        symbol=symbol,
        last=Decimal("100"),
        observed_at=Instant.now(),
        quality=DataQuality(
            source=Provenance(venue_id="kucoin", endpoint="fetch_ticker"),
            fetched_at=Instant.now(),
            staleness=Staleness.FRESH,
            confidence=Confidence.HIGH,
            cache_hit=True,
        ),
    )


class TestSupabaseCacheHandler:
    @pytest.mark.asyncio
    async def test_cache_hit_short_circuits(self, btc_symbol) -> None:
        cached = _make_cached_ticker(btc_symbol)
        gateway = MagicMock()
        gateway.load_ticker = AsyncMock(return_value=cached)
        req = FetchRequest(operation=FetchOperation.TICKER, symbol=btc_symbol)
        ctx = FetchContext(request=req)
        handler = SupabaseCacheHandler(gateway)
        result = await handler.handle(ctx)
        assert result.metadata["result"] is cached
        assert "cache:hit" in ctx.reason_codes
        gateway.load_ticker.assert_awaited_once_with(btc_symbol)

    @pytest.mark.asyncio
    async def test_cache_miss_forwards(self, btc_symbol) -> None:
        gateway = MagicMock()
        gateway.load_ticker = AsyncMock(return_value=None)
        req = FetchRequest(operation=FetchOperation.TICKER, symbol=btc_symbol)
        ctx = FetchContext(request=req)
        handler = SupabaseCacheHandler(gateway)
        result = await handler.handle(ctx)
        assert result is ctx
        assert "cache:miss" in ctx.reason_codes
        assert not ctx.has_result()

    @pytest.mark.asyncio
    async def test_bypass_cache_skips_lookup(self, btc_symbol) -> None:
        gateway = MagicMock()
        gateway.load_ticker = AsyncMock(return_value="unused")
        req = FetchRequest(
            operation=FetchOperation.TICKER,
            symbol=btc_symbol,
            force_refresh=True,
        )
        ctx = FetchContext(request=req)
        ctx.metadata["bypass_cache"] = True
        handler = SupabaseCacheHandler(gateway)
        result = await handler.handle(ctx)
        assert result is ctx
        assert not ctx.has_result()
        gateway.load_ticker.assert_not_called()

    @pytest.mark.asyncio
    async def test_gateway_error_falls_through(self, btc_symbol) -> None:
        gateway = MagicMock()
        gateway.load_ticker = AsyncMock(
            side_effect=RuntimeError("connection lost"),
        )
        req = FetchRequest(operation=FetchOperation.TICKER, symbol=btc_symbol)
        ctx = FetchContext(request=req)
        handler = SupabaseCacheHandler(gateway)
        result = await handler.handle(ctx)
        assert result is ctx
        assert "cache:error" in ctx.reason_codes
        assert not ctx.has_result()

    @pytest.mark.asyncio
    async def test_ohlcv_cache_hit(self, btc_symbol) -> None:
        gateway = MagicMock()
        cached_series = MagicMock()
        gateway.load_ohlcv = AsyncMock(return_value=cached_series)
        req = FetchRequest(
            operation=FetchOperation.OHLCV,
            symbol=btc_symbol,
            timeframe=Timeframe.H1,
            limit=100,
        )
        ctx = FetchContext(request=req)
        handler = SupabaseCacheHandler(gateway)
        result = await handler.handle(ctx)
        assert result.metadata["result"] is cached_series
        gateway.load_ohlcv.assert_awaited_once_with(
            btc_symbol,
            Timeframe.H1,
            since=None,
            limit=100,
        )


class _FakeProvider:
    venue_id = "kucoin"

    def __init__(self) -> None:
        self.ticker_calls = 0
        self.ohlcv_calls = 0

    async def fetch_ticker(self, symbol):
        self.ticker_calls += 1
        return _make_cached_ticker(symbol)

    async def fetch_ohlcv(self, symbol, timeframe, since=None, limit=500):
        self.ohlcv_calls += 1
        return f"ohlcv-{symbol.native_symbol}-{timeframe.value}"


class TestProviderFetchHandler:
    @pytest.mark.asyncio
    async def test_cache_hit_skips_provider(self, btc_symbol) -> None:
        provider = _FakeProvider()
        gateway = MagicMock()
        gateway.upsert_ticker = AsyncMock()
        req = FetchRequest(operation=FetchOperation.TICKER, symbol=btc_symbol)
        ctx = FetchContext(request=req)
        ctx.metadata["result"] = "cached-ticker"
        handler = ProviderFetchHandler(provider=provider, gateway=gateway)
        result = await handler.handle(ctx)
        assert result.metadata["result"] == "cached-ticker"
        assert provider.ticker_calls == 0
        gateway.upsert_ticker.assert_not_called()

    @pytest.mark.asyncio
    async def test_ticker_miss_calls_provider_and_upserts(
        self,
        btc_symbol,
    ) -> None:
        provider = _FakeProvider()
        gateway = MagicMock()
        gateway.upsert_ticker = AsyncMock()
        req = FetchRequest(operation=FetchOperation.TICKER, symbol=btc_symbol)
        ctx = FetchContext(request=req)
        handler = ProviderFetchHandler(provider=provider, gateway=gateway)
        result = await handler.handle(ctx)
        assert result.metadata["result"] is not None
        assert provider.ticker_calls == 1
        assert "provider:called" in ctx.reason_codes
        gateway.upsert_ticker.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ohlcv_miss_calls_provider(self, btc_symbol) -> None:
        provider = _FakeProvider()
        gateway = MagicMock()
        gateway.upsert_ohlcv = AsyncMock()
        req = FetchRequest(
            operation=FetchOperation.OHLCV,
            symbol=btc_symbol,
            timeframe=Timeframe.H1,
            limit=50,
        )
        ctx = FetchContext(request=req)
        handler = ProviderFetchHandler(provider=provider, gateway=gateway)
        result = await handler.handle(ctx)
        assert "ohlcv-BTC-USDT-1h" in result.metadata["result"]
        assert provider.ohlcv_calls == 1
        gateway.upsert_ohlcv.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upsert_failure_does_not_break_response(
        self,
        btc_symbol,
    ) -> None:
        provider = _FakeProvider()
        gateway = MagicMock()
        gateway.upsert_ticker = AsyncMock(side_effect=RuntimeError("db down"))
        req = FetchRequest(operation=FetchOperation.TICKER, symbol=btc_symbol)
        ctx = FetchContext(request=req)
        handler = ProviderFetchHandler(provider=provider, gateway=gateway)
        # Should still succeed; write-through failure logged, not raised
        result = await handler.handle(ctx)
        assert result.metadata["result"] is not None
        assert "provider:called" in ctx.reason_codes
        assert "cache:write_failed" in ctx.reason_codes
