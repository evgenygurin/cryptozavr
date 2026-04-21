"""Test TickerDTO construction and from_domain factory."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.domain.market_data import Ticker
from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.mcp.dtos import TickerDTO


@pytest.fixture
def btc_ticker() -> Ticker:
    symbol = SymbolRegistry().get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )
    return Ticker(
        symbol=symbol,
        last=Decimal("50000.5"),
        bid=Decimal("50000.0"),
        ask=Decimal("50001.0"),
        volume_24h=Decimal("1234.5"),
        observed_at=Instant.from_ms(1_700_000_000_000),
        quality=DataQuality(
            source=Provenance(venue_id="kucoin", endpoint="fetch_ticker"),
            fetched_at=Instant.from_ms(1_700_000_000_000),
            staleness=Staleness.FRESH,
            confidence=Confidence.HIGH,
            cache_hit=False,
        ),
    )


class TestTickerDTO:
    def test_from_domain_copies_core_fields(self, btc_ticker: Ticker) -> None:
        dto = TickerDTO.from_domain(btc_ticker, reason_codes=["venue:healthy"])
        assert dto.venue == "kucoin"
        assert dto.symbol == "BTC-USDT"
        assert dto.last == Decimal("50000.5")
        assert dto.bid == Decimal("50000.0")
        assert dto.ask == Decimal("50001.0")
        assert dto.volume_24h == Decimal("1234.5")
        assert dto.observed_at_ms == 1_700_000_000_000
        assert dto.staleness == "fresh"
        assert dto.confidence == "high"
        assert dto.cache_hit is False
        assert dto.reason_codes == ["venue:healthy"]

    def test_from_domain_handles_missing_optional_fields(
        self,
        btc_ticker: Ticker,
    ) -> None:
        stripped = btc_ticker.__class__(
            symbol=btc_ticker.symbol,
            last=btc_ticker.last,
            observed_at=btc_ticker.observed_at,
            quality=btc_ticker.quality,
        )
        dto = TickerDTO.from_domain(stripped, reason_codes=[])
        assert dto.bid is None
        assert dto.ask is None
        assert dto.volume_24h is None

    def test_dto_serializes_to_json(self, btc_ticker: Ticker) -> None:
        dto = TickerDTO.from_domain(btc_ticker, reason_codes=["cache:hit"])
        payload = dto.model_dump(mode="json")
        assert payload["venue"] == "kucoin"
        assert payload["symbol"] == "BTC-USDT"
        assert payload["last"] == "50000.5"  # Decimal → str in JSON mode
        assert payload["reason_codes"] == ["cache:hit"]
