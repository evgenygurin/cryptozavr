"""Test market data entities."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.domain.market_data import Ticker, TradeSide
from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.symbols import Symbol, SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Percentage
from cryptozavr.domain.venues import MarketType, VenueId


@pytest.fixture
def registry() -> SymbolRegistry:
    return SymbolRegistry()


@pytest.fixture
def btc_usdt(registry: SymbolRegistry) -> Symbol:
    return registry.get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )


@pytest.fixture
def fresh_quality() -> DataQuality:
    return DataQuality(
        source=Provenance(venue_id="kucoin", endpoint="fetch_ticker"),
        fetched_at=Instant.now(),
        staleness=Staleness.FRESH,
        confidence=Confidence.HIGH,
        cache_hit=False,
    )


class TestTradeSide:
    def test_values(self) -> None:
        assert TradeSide.BUY.value == "buy"
        assert TradeSide.SELL.value == "sell"
        assert TradeSide.UNKNOWN.value == "unknown"


class TestTicker:
    def test_happy_path(self, btc_usdt: Symbol, fresh_quality: DataQuality) -> None:
        t = Ticker(
            symbol=btc_usdt,
            last=Decimal("65000.50"),
            bid=Decimal("64999.50"),
            ask=Decimal("65001.50"),
            volume_24h=Decimal("1234.56"),
            change_24h_pct=Percentage(value=Decimal("2.5")),
            high_24h=Decimal("66000"),
            low_24h=Decimal("64000"),
            observed_at=Instant.now(),
            quality=fresh_quality,
        )
        assert t.last == Decimal("65000.50")
        assert t.bid == Decimal("64999.50")

    def test_minimal(self, btc_usdt: Symbol, fresh_quality: DataQuality) -> None:
        t = Ticker(
            symbol=btc_usdt,
            last=Decimal("65000"),
            observed_at=Instant.now(),
            quality=fresh_quality,
        )
        assert t.bid is None
        assert t.ask is None
        assert t.volume_24h is None
