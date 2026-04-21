"""Test TradesService: venue/symbol validation + chain wiring."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from cryptozavr.application.services.trades_service import (
    TradesFetchResult,
    TradesService,
)
from cryptozavr.domain.exceptions import (
    SymbolNotFoundError,
    VenueNotSupportedError,
)
from cryptozavr.domain.market_data import TradeSide, TradeTick
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.state.venue_state import VenueState


def _make_trades(symbol) -> tuple[TradeTick, ...]:
    return (
        TradeTick(
            symbol=symbol,
            price=Decimal("100"),
            size=Decimal("0.5"),
            side=TradeSide.BUY,
            executed_at=Instant.from_ms(1_700_000_000_000),
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
    p.fetch_trades = AsyncMock(return_value=_make_trades(symbol))
    return p


@pytest.fixture
def gateway():
    gw = MagicMock()
    gw.load_ticker = AsyncMock(return_value=None)
    gw.load_ohlcv = AsyncMock(return_value=None)
    return gw


@pytest.fixture
def service(registry, gateway, provider) -> TradesService:
    return TradesService(
        registry=registry,
        venue_states={VenueId.KUCOIN: VenueState(VenueId.KUCOIN)},
        providers={VenueId.KUCOIN: provider},
        gateway=gateway,
    )


class TestTradesService:
    @pytest.mark.asyncio
    async def test_fetch_trades_returns_result(
        self,
        service: TradesService,
    ) -> None:
        result = await service.fetch_trades(
            venue="kucoin",
            symbol="BTC-USDT",
            limit=100,
        )
        assert isinstance(result, TradesFetchResult)
        assert len(result.trades) == 1
        assert result.venue == "kucoin"
        assert result.symbol == "BTC-USDT"
        assert "provider:called" in result.reason_codes

    @pytest.mark.asyncio
    async def test_forwards_limit_and_since(
        self,
        service: TradesService,
        provider,
    ) -> None:
        since = Instant.from_ms(1_700_000_000_000)
        await service.fetch_trades(
            venue="kucoin",
            symbol="BTC-USDT",
            limit=50,
            since=since,
        )
        call_kwargs = provider.fetch_trades.call_args.kwargs
        assert call_kwargs.get("limit") == 50
        assert call_kwargs.get("since") == since

    @pytest.mark.asyncio
    async def test_force_refresh_passes_through(
        self,
        service: TradesService,
        provider,
    ) -> None:
        result = await service.fetch_trades(
            venue="kucoin",
            symbol="BTC-USDT",
            limit=100,
            force_refresh=True,
        )
        assert "cache:bypassed" in result.reason_codes
        provider.fetch_trades.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unknown_venue_raises(
        self,
        service: TradesService,
    ) -> None:
        with pytest.raises(VenueNotSupportedError):
            await service.fetch_trades(
                venue="binance",
                symbol="BTC-USDT",
                limit=100,
            )

    @pytest.mark.asyncio
    async def test_unknown_symbol_raises(
        self,
        service: TradesService,
    ) -> None:
        with pytest.raises(SymbolNotFoundError):
            await service.fetch_trades(
                venue="kucoin",
                symbol="DOGE-USDT",
                limit=100,
            )
