"""Test TickerDTO construction and from_domain factory."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.domain.market_data import (
    OHLCVCandle,
    OHLCVSeries,
    OrderBookSnapshot,
    Ticker,
    TradeSide,
    TradeTick,
)
from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, PriceSize, Timeframe, TimeRange
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.mcp.dtos import (
    OHLCVCandleDTO,
    OHLCVSeriesDTO,
    OrderBookDTO,
    PriceSizeDTO,
    TickerDTO,
    TradesDTO,
    TradeTickDTO,
)


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


@pytest.fixture
def btc_orderbook() -> OrderBookSnapshot:
    symbol = SymbolRegistry().get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )
    bids = (
        PriceSize(price=Decimal("100"), size=Decimal("1.5")),
        PriceSize(price=Decimal("99.5"), size=Decimal("2.0")),
    )
    asks = (
        PriceSize(price=Decimal("101"), size=Decimal("1.0")),
        PriceSize(price=Decimal("101.5"), size=Decimal("3.0")),
    )
    return OrderBookSnapshot(
        symbol=symbol,
        bids=bids,
        asks=asks,
        observed_at=Instant.from_ms(1_700_000_000_000),
        quality=DataQuality(
            source=Provenance(venue_id="kucoin", endpoint="fetch_order_book"),
            fetched_at=Instant.from_ms(1_700_000_000_000),
            staleness=Staleness.FRESH,
            confidence=Confidence.HIGH,
            cache_hit=False,
        ),
    )


@pytest.fixture
def btc_trades() -> tuple[TradeTick, ...]:
    symbol = SymbolRegistry().get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )
    return (
        TradeTick(
            symbol=symbol,
            price=Decimal("100.5"),
            size=Decimal("0.1"),
            side=TradeSide.BUY,
            executed_at=Instant.from_ms(1_700_000_000_000),
            trade_id="t1",
        ),
        TradeTick(
            symbol=symbol,
            price=Decimal("100.6"),
            size=Decimal("0.2"),
            side=TradeSide.SELL,
            executed_at=Instant.from_ms(1_700_000_001_000),
        ),
    )


class TestPriceSizeDTO:
    def test_from_domain_copies_price_and_size(self) -> None:
        ps = PriceSize(price=Decimal("100"), size=Decimal("1.5"))
        dto = PriceSizeDTO.from_domain(ps)
        assert dto.price == Decimal("100")
        assert dto.size == Decimal("1.5")


class TestOrderBookDTO:
    def test_from_domain_copies_fields(
        self,
        btc_orderbook: OrderBookSnapshot,
    ) -> None:
        dto = OrderBookDTO.from_domain(
            btc_orderbook,
            reason_codes=["venue:healthy"],
        )
        assert dto.venue == "kucoin"
        assert dto.symbol == "BTC-USDT"
        assert dto.observed_at_ms == 1_700_000_000_000
        assert len(dto.bids) == 2
        assert len(dto.asks) == 2
        assert dto.bids[0].price == Decimal("100")
        assert dto.asks[0].price == Decimal("101")
        assert dto.spread == Decimal("1")
        assert dto.spread_bps is not None
        assert dto.cache_hit is False
        assert dto.reason_codes == ["venue:healthy"]

    def test_from_domain_empty_book_spread_is_none(self) -> None:
        symbol = SymbolRegistry().get(
            VenueId.KUCOIN,
            "BTC",
            "USDT",
            market_type=MarketType.SPOT,
            native_symbol="BTC-USDT",
        )
        empty = OrderBookSnapshot(
            symbol=symbol,
            bids=(),
            asks=(),
            observed_at=Instant.from_ms(1),
            quality=DataQuality(
                source=Provenance(
                    venue_id="kucoin",
                    endpoint="fetch_order_book",
                ),
                fetched_at=Instant.from_ms(1),
                staleness=Staleness.FRESH,
                confidence=Confidence.HIGH,
                cache_hit=False,
            ),
        )
        dto = OrderBookDTO.from_domain(empty, reason_codes=[])
        assert dto.spread is None
        assert dto.spread_bps is None
        assert dto.bids == []
        assert dto.asks == []


class TestTradeTickDTO:
    def test_from_domain_copies_fields(
        self,
        btc_trades: tuple[TradeTick, ...],
    ) -> None:
        dto = TradeTickDTO.from_domain(btc_trades[0])
        assert dto.price == Decimal("100.5")
        assert dto.size == Decimal("0.1")
        assert dto.side == "buy"
        assert dto.executed_at_ms == 1_700_000_000_000
        assert dto.trade_id == "t1"

    def test_from_domain_handles_missing_trade_id(
        self,
        btc_trades: tuple[TradeTick, ...],
    ) -> None:
        dto = TradeTickDTO.from_domain(btc_trades[1])
        assert dto.trade_id is None
        assert dto.side == "sell"


class TestTradesDTO:
    def test_from_domain_copies_fields(
        self,
        btc_trades: tuple[TradeTick, ...],
    ) -> None:
        dto = TradesDTO.from_domain(
            venue="kucoin",
            symbol="BTC-USDT",
            trades=btc_trades,
            reason_codes=["venue:healthy", "cache:miss", "provider:called"],
        )
        assert dto.venue == "kucoin"
        assert dto.symbol == "BTC-USDT"
        assert len(dto.trades) == 2
        assert dto.trades[0].trade_id == "t1"
        assert dto.reason_codes == [
            "venue:healthy",
            "cache:miss",
            "provider:called",
        ]

    def test_empty_trades_list(self) -> None:
        dto = TradesDTO.from_domain(
            venue="kucoin",
            symbol="BTC-USDT",
            trades=(),
            reason_codes=[],
        )
        assert dto.trades == []
