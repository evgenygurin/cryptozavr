"""Test TickerService: venue/symbol validation + chain wiring + fetch result."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from cryptozavr.application.services.ticker_service import (
    TickerFetchResult,
    TickerService,
)
from cryptozavr.domain.exceptions import (
    SymbolNotFoundError,
    VenueNotSupportedError,
)
from cryptozavr.domain.market_data import Ticker
from cryptozavr.domain.quality import (
    Confidence,
    DataQuality,
    Provenance,
    Staleness,
)
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.state.venue_state import VenueState


def _make_ticker(symbol) -> Ticker:
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
def provider_factory_output(registry: SymbolRegistry):
    """Build a provider whose fetch_ticker returns a canned Ticker."""
    symbol = registry.find(VenueId.KUCOIN, "BTC-USDT")
    assert symbol is not None
    provider = MagicMock()
    provider.fetch_ticker = AsyncMock(return_value=_make_ticker(symbol))
    return provider


@pytest.fixture
def gateway():
    gw = MagicMock()
    gw.load_ticker = AsyncMock(return_value=None)  # cache miss by default
    gw.upsert_ticker = AsyncMock()
    return gw


@pytest.fixture
def service(registry, gateway, provider_factory_output) -> TickerService:
    return TickerService(
        registry=registry,
        venue_states={VenueId.KUCOIN: VenueState(VenueId.KUCOIN)},
        providers={VenueId.KUCOIN: provider_factory_output},
        gateway=gateway,
    )


class TestTickerService:
    @pytest.mark.asyncio
    async def test_fetch_ticker_returns_fetch_result_with_reasons(
        self,
        service: TickerService,
    ) -> None:
        result = await service.fetch_ticker(venue="kucoin", symbol="BTC-USDT")
        assert isinstance(result, TickerFetchResult)
        assert result.ticker.last == Decimal("100")
        assert "venue:healthy" in result.reason_codes
        assert "provider:called" in result.reason_codes

    @pytest.mark.asyncio
    async def test_cache_hit_skips_provider(
        self,
        registry,
        gateway,
        provider_factory_output,
    ) -> None:
        symbol = registry.find(VenueId.KUCOIN, "BTC-USDT")
        assert symbol is not None
        cached = _make_ticker(symbol)
        gateway.load_ticker = AsyncMock(return_value=cached)
        service = TickerService(
            registry=registry,
            venue_states={VenueId.KUCOIN: VenueState(VenueId.KUCOIN)},
            providers={VenueId.KUCOIN: provider_factory_output},
            gateway=gateway,
        )
        result = await service.fetch_ticker(venue="kucoin", symbol="BTC-USDT")
        assert result.ticker is cached
        assert "cache:hit" in result.reason_codes
        provider_factory_output.fetch_ticker.assert_not_called()

    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_cache(
        self,
        registry,
        gateway,
        provider_factory_output,
    ) -> None:
        symbol = registry.find(VenueId.KUCOIN, "BTC-USDT")
        assert symbol is not None
        gateway.load_ticker = AsyncMock(return_value=_make_ticker(symbol))
        service = TickerService(
            registry=registry,
            venue_states={VenueId.KUCOIN: VenueState(VenueId.KUCOIN)},
            providers={VenueId.KUCOIN: provider_factory_output},
            gateway=gateway,
        )
        result = await service.fetch_ticker(
            venue="kucoin",
            symbol="BTC-USDT",
            force_refresh=True,
        )
        assert "cache:bypassed" in result.reason_codes
        provider_factory_output.fetch_ticker.assert_awaited_once()
        gateway.load_ticker.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_venue_string_raises_venue_not_supported(
        self,
        service: TickerService,
    ) -> None:
        with pytest.raises(VenueNotSupportedError):
            await service.fetch_ticker(venue="binance", symbol="BTC-USDT")

    @pytest.mark.asyncio
    async def test_unknown_symbol_raises_symbol_not_found(
        self,
        service: TickerService,
    ) -> None:
        with pytest.raises(SymbolNotFoundError):
            await service.fetch_ticker(venue="kucoin", symbol="DOGE-USDT")
