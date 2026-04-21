"""Test TickerDTO construction and from_domain factory."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.domain.market_data import OHLCVCandle, OHLCVSeries, Ticker
from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Timeframe, TimeRange
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.mcp.dtos import OHLCVCandleDTO, OHLCVSeriesDTO, TickerDTO


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


@pytest.fixture
def btc_series() -> OHLCVSeries:
    symbol = SymbolRegistry().get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )
    candles = (
        OHLCVCandle(
            opened_at=Instant.from_ms(1_700_000_000_000),
            open=Decimal("100"),
            high=Decimal("110"),
            low=Decimal("95"),
            close=Decimal("105"),
            volume=Decimal("1000"),
        ),
        OHLCVCandle(
            opened_at=Instant.from_ms(1_700_000_060_000),
            open=Decimal("105"),
            high=Decimal("120"),
            low=Decimal("100"),
            close=Decimal("115"),
            volume=Decimal("2000"),
            closed=False,
        ),
    )
    return OHLCVSeries(
        symbol=symbol,
        timeframe=Timeframe.M1,
        candles=candles,
        range=TimeRange(
            start=Instant.from_ms(1_700_000_000_000),
            end=Instant.from_ms(1_700_000_120_000),
        ),
        quality=DataQuality(
            source=Provenance(venue_id="kucoin", endpoint="fetch_ohlcv"),
            fetched_at=Instant.from_ms(1_700_000_120_000),
            staleness=Staleness.FRESH,
            confidence=Confidence.HIGH,
            cache_hit=False,
        ),
    )


class TestOHLCVCandleDTO:
    def test_from_domain_copies_fields(self, btc_series: OHLCVSeries) -> None:
        dto = OHLCVCandleDTO.from_domain(btc_series.candles[0])
        assert dto.opened_at_ms == 1_700_000_000_000
        assert dto.open == Decimal("100")
        assert dto.high == Decimal("110")
        assert dto.low == Decimal("95")
        assert dto.close == Decimal("105")
        assert dto.volume == Decimal("1000")
        assert dto.closed is True

    def test_closed_false_flag_preserved(
        self,
        btc_series: OHLCVSeries,
    ) -> None:
        dto = OHLCVCandleDTO.from_domain(btc_series.candles[1])
        assert dto.closed is False


class TestOHLCVSeriesDTO:
    def test_from_domain_copies_fields(self, btc_series: OHLCVSeries) -> None:
        dto = OHLCVSeriesDTO.from_domain(
            btc_series,
            reason_codes=["venue:healthy", "cache:miss"],
        )
        assert dto.venue == "kucoin"
        assert dto.symbol == "BTC-USDT"
        assert dto.timeframe == "1m"
        assert dto.range_start_ms == 1_700_000_000_000
        assert dto.range_end_ms == 1_700_000_120_000
        assert len(dto.candles) == 2
        assert dto.candles[0].open == Decimal("100")
        assert dto.cache_hit is False
        assert dto.reason_codes == ["venue:healthy", "cache:miss"]

    def test_dto_serializes_to_json(self, btc_series: OHLCVSeries) -> None:
        dto = OHLCVSeriesDTO.from_domain(btc_series, reason_codes=[])
        payload = dto.model_dump(mode="json")
        assert payload["timeframe"] == "1m"
        assert len(payload["candles"]) == 2
        assert payload["candles"][0]["open"] == "100"
