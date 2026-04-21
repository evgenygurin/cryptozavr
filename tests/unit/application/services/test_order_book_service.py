"""Test OrderBookService: venue/symbol validation + chain wiring."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from cryptozavr.application.services.order_book_service import (
    OrderBookFetchResult,
    OrderBookService,
)
from cryptozavr.domain.exceptions import (
    SymbolNotFoundError,
    VenueNotSupportedError,
)
from cryptozavr.domain.market_data import OrderBookSnapshot
from cryptozavr.domain.quality import (
    Confidence,
    DataQuality,
    Provenance,
    Staleness,
)
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, PriceSize
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.state.venue_state import VenueState


def _make_snapshot(symbol) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        symbol=symbol,
        bids=(PriceSize(price=Decimal("100"), size=Decimal("1")),),
        asks=(PriceSize(price=Decimal("101"), size=Decimal("1")),),
        observed_at=Instant.now(),
        quality=DataQuality(
            source=Provenance(
                venue_id="kucoin",
                endpoint="fetch_order_book",
            ),
            fetched_at=Instant.now(),
            staleness=Staleness.FRESH,
            confidence=Confidence.HIGH,
            cache_hit=False,
        ),
    )


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
def provider(registry: SymbolRegistry):
    symbol = registry.find(VenueId.KUCOIN, "BTC-USDT")
    assert symbol is not None
    p = MagicMock()
    p.fetch_order_book = AsyncMock(return_value=_make_snapshot(symbol))
    return p


@pytest.fixture
def gateway():
    gw = MagicMock()
    gw.load_ticker = AsyncMock(return_value=None)
    gw.load_ohlcv = AsyncMock(return_value=None)
    return gw


@pytest.fixture
def service(registry, gateway, provider) -> OrderBookService:
    return OrderBookService(
        registry=registry,
        venue_states={VenueId.KUCOIN: VenueState(VenueId.KUCOIN)},
        providers={VenueId.KUCOIN: provider},
        gateway=gateway,
    )


class TestOrderBookService:
    @pytest.mark.asyncio
    async def test_fetch_order_book_returns_result(
        self,
        service: OrderBookService,
    ) -> None:
        result = await service.fetch_order_book(
            venue="kucoin",
            symbol="BTC-USDT",
            depth=50,
        )
        assert isinstance(result, OrderBookFetchResult)
        assert len(result.snapshot.bids) == 1
        assert len(result.snapshot.asks) == 1
        assert "provider:called" in result.reason_codes

    @pytest.mark.asyncio
    async def test_forwards_depth_to_provider(
        self,
        service: OrderBookService,
        provider,
    ) -> None:
        await service.fetch_order_book(
            venue="kucoin",
            symbol="BTC-USDT",
            depth=20,
        )
        provider.fetch_order_book.assert_awaited_once()
        call_kwargs = provider.fetch_order_book.call_args.kwargs
        assert call_kwargs.get("depth") == 20

    @pytest.mark.asyncio
    async def test_force_refresh_passes_through(
        self,
        service: OrderBookService,
        provider,
    ) -> None:
        result = await service.fetch_order_book(
            venue="kucoin",
            symbol="BTC-USDT",
            depth=50,
            force_refresh=True,
        )
        assert "cache:bypassed" in result.reason_codes
        provider.fetch_order_book.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unknown_venue_raises(
        self,
        service: OrderBookService,
    ) -> None:
        with pytest.raises(VenueNotSupportedError):
            await service.fetch_order_book(
                venue="binance",
                symbol="BTC-USDT",
                depth=50,
            )

    @pytest.mark.asyncio
    async def test_unknown_symbol_raises(
        self,
        service: OrderBookService,
    ) -> None:
        with pytest.raises(SymbolNotFoundError):
            await service.fetch_order_book(
                venue="kucoin",
                symbol="DOGE-USDT",
                depth=50,
            )
