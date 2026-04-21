"""Test OhlcvService: venue/symbol validation + chain wiring."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from cryptozavr.application.services.ohlcv_service import (
    OhlcvFetchResult,
    OhlcvService,
)
from cryptozavr.domain.exceptions import (
    SymbolNotFoundError,
    VenueNotSupportedError,
)
from cryptozavr.domain.market_data import OHLCVCandle, OHLCVSeries
from cryptozavr.domain.quality import (
    Confidence,
    DataQuality,
    Provenance,
    Staleness,
)
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Timeframe, TimeRange
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.state.venue_state import VenueState


def _make_series(symbol) -> OHLCVSeries:
    candle = OHLCVCandle(
        opened_at=Instant.from_ms(1_700_000_000_000),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("95"),
        close=Decimal("105"),
        volume=Decimal("1000"),
    )
    return OHLCVSeries(
        symbol=symbol,
        timeframe=Timeframe.M1,
        candles=(candle,),
        range=TimeRange(
            start=Instant.from_ms(1_700_000_000_000),
            end=Instant.from_ms(1_700_000_060_000),
        ),
        quality=DataQuality(
            source=Provenance(venue_id="kucoin", endpoint="fetch_ohlcv"),
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
    p.fetch_ohlcv = AsyncMock(return_value=_make_series(symbol))
    return p


@pytest.fixture
def gateway():
    gw = MagicMock()
    gw.load_ohlcv = AsyncMock(return_value=None)
    gw.upsert_ohlcv = AsyncMock(return_value=1)
    return gw


@pytest.fixture
def service(registry, gateway, provider) -> OhlcvService:
    return OhlcvService(
        registry=registry,
        venue_states={VenueId.KUCOIN: VenueState(VenueId.KUCOIN)},
        providers={VenueId.KUCOIN: provider},
        gateway=gateway,
    )


class TestOhlcvService:
    @pytest.mark.asyncio
    async def test_fetch_ohlcv_returns_fetch_result(
        self,
        service: OhlcvService,
    ) -> None:
        result = await service.fetch_ohlcv(
            venue="kucoin",
            symbol="BTC-USDT",
            timeframe=Timeframe.M1,
            limit=100,
        )
        assert isinstance(result, OhlcvFetchResult)
        assert len(result.series.candles) == 1
        assert "provider:called" in result.reason_codes

    @pytest.mark.asyncio
    async def test_cache_hit_skips_provider(
        self,
        registry,
        gateway,
        provider,
    ) -> None:
        symbol = registry.find(VenueId.KUCOIN, "BTC-USDT")
        assert symbol is not None
        cached = _make_series(symbol)
        gateway.load_ohlcv = AsyncMock(return_value=cached)
        service = OhlcvService(
            registry=registry,
            venue_states={VenueId.KUCOIN: VenueState(VenueId.KUCOIN)},
            providers={VenueId.KUCOIN: provider},
            gateway=gateway,
        )
        result = await service.fetch_ohlcv(
            venue="kucoin",
            symbol="BTC-USDT",
            timeframe=Timeframe.M1,
            limit=100,
        )
        assert result.series is cached
        assert "cache:hit" in result.reason_codes
        provider.fetch_ohlcv.assert_not_called()

    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_cache(
        self,
        registry,
        gateway,
        provider,
    ) -> None:
        symbol = registry.find(VenueId.KUCOIN, "BTC-USDT")
        assert symbol is not None
        gateway.load_ohlcv = AsyncMock(return_value=_make_series(symbol))
        service = OhlcvService(
            registry=registry,
            venue_states={VenueId.KUCOIN: VenueState(VenueId.KUCOIN)},
            providers={VenueId.KUCOIN: provider},
            gateway=gateway,
        )
        result = await service.fetch_ohlcv(
            venue="kucoin",
            symbol="BTC-USDT",
            timeframe=Timeframe.M1,
            limit=100,
            force_refresh=True,
        )
        assert "cache:bypassed" in result.reason_codes
        provider.fetch_ohlcv.assert_awaited_once()
        gateway.load_ohlcv.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_venue_raises_venue_not_supported(
        self,
        service: OhlcvService,
    ) -> None:
        with pytest.raises(VenueNotSupportedError):
            await service.fetch_ohlcv(
                venue="binance",
                symbol="BTC-USDT",
                timeframe=Timeframe.M1,
                limit=100,
            )

    @pytest.mark.asyncio
    async def test_unknown_symbol_raises_symbol_not_found(
        self,
        service: OhlcvService,
    ) -> None:
        with pytest.raises(SymbolNotFoundError):
            await service.fetch_ohlcv(
                venue="kucoin",
                symbol="DOGE-USDT",
                timeframe=Timeframe.M1,
                limit=100,
            )
