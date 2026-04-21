"""Test chain assembly helpers."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from cryptozavr.domain.market_data import Ticker
from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Timeframe
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.chain.assembly import (
    build_ohlcv_chain,
    build_ticker_chain,
)
from cryptozavr.infrastructure.providers.chain.context import (
    FetchContext,
    FetchOperation,
    FetchRequest,
)
from cryptozavr.infrastructure.providers.state.venue_state import VenueState


@pytest.fixture
def registry() -> SymbolRegistry:
    reg = SymbolRegistry()
    reg.get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )
    return reg


@pytest.fixture
def btc_symbol(registry):
    return registry.get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )


class _FakeProvider:
    venue_id = "kucoin"

    async def fetch_ticker(self, symbol):
        return Ticker(
            symbol=symbol,
            last=Decimal("100"),
            observed_at=Instant.now(),
            quality=DataQuality(
                source=Provenance(venue_id="kucoin", endpoint="fetch_ticker"),
                fetched_at=Instant.now(),
                staleness=Staleness.FRESH,
                confidence=Confidence.HIGH,
                cache_hit=False,
            ),
        )

    async def fetch_ohlcv(self, symbol, timeframe, since=None, limit=500):
        return f"ohlcv-{symbol.native_symbol}"


@pytest.mark.asyncio
async def test_ticker_chain_cache_miss_then_provider(
    btc_symbol,
    registry,
) -> None:
    gateway = MagicMock()
    gateway.load_ticker = AsyncMock(return_value=None)  # miss
    gateway.upsert_ticker = AsyncMock()

    chain = build_ticker_chain(
        state=VenueState(VenueId.KUCOIN),
        registry=registry,
        gateway=gateway,
        provider=_FakeProvider(),
    )

    ctx = FetchContext(
        request=FetchRequest(
            operation=FetchOperation.TICKER,
            symbol=btc_symbol,
        ),
    )
    result = await chain.handle(ctx)

    assert result.has_result()
    assert ctx.reason_codes == [
        "venue:healthy",
        "symbol:found",
        "cache:miss",
        "provider:called",
    ]
    gateway.load_ticker.assert_awaited_once()
    gateway.upsert_ticker.assert_awaited_once()


@pytest.mark.asyncio
async def test_ticker_chain_cache_hit_short_circuits(
    btc_symbol,
    registry,
) -> None:
    cached_ticker = Ticker(
        symbol=btc_symbol,
        last=Decimal("99"),
        observed_at=Instant.now(),
        quality=DataQuality(
            source=Provenance(venue_id="kucoin", endpoint="fetch_ticker"),
            fetched_at=Instant.now(),
            staleness=Staleness.FRESH,
            confidence=Confidence.HIGH,
            cache_hit=True,
        ),
    )
    gateway = MagicMock()
    gateway.load_ticker = AsyncMock(return_value=cached_ticker)
    gateway.upsert_ticker = AsyncMock()

    chain = build_ticker_chain(
        state=VenueState(VenueId.KUCOIN),
        registry=registry,
        gateway=gateway,
        provider=_FakeProvider(),
    )

    ctx = FetchContext(
        request=FetchRequest(
            operation=FetchOperation.TICKER,
            symbol=btc_symbol,
        ),
    )
    result = await chain.handle(ctx)

    assert result.metadata["result"] is cached_ticker
    assert "cache:hit" in ctx.reason_codes
    assert "provider:called" not in ctx.reason_codes
    gateway.upsert_ticker.assert_not_called()


@pytest.mark.asyncio
async def test_ohlcv_chain_assembles_correctly(
    btc_symbol,
    registry,
) -> None:
    gateway = MagicMock()
    gateway.load_ohlcv = AsyncMock(return_value=None)
    gateway.upsert_ohlcv = AsyncMock()

    chain = build_ohlcv_chain(
        state=VenueState(VenueId.KUCOIN),
        registry=registry,
        gateway=gateway,
        provider=_FakeProvider(),
    )

    ctx = FetchContext(
        request=FetchRequest(
            operation=FetchOperation.OHLCV,
            symbol=btc_symbol,
            timeframe=Timeframe.H1,
            limit=10,
        ),
    )
    result = await chain.handle(ctx)

    assert result.has_result()
    assert "provider:called" in ctx.reason_codes
