"""Test TickerDTO construction and from_domain factory."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.application.services.market_analyzer import AnalysisReport
from cryptozavr.application.strategies.base import AnalysisResult
from cryptozavr.domain.assets import Asset, AssetCategory
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
    AnalysisReportDTO,
    AnalysisResultDTO,
    CategoryDTO,
    OHLCVCandleDTO,
    OHLCVHistoryDTO,
    OHLCVSeriesDTO,
    OrderBookDTO,
    PriceSizeDTO,
    SymbolDTO,
    TickerDTO,
    TradesDTO,
    TradeTickDTO,
    TrendingAssetDTO,
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


class TestOHLCVHistoryDTO:
    def test_from_chunks_builds_wire_payload(self) -> None:
        candles = [
            OHLCVCandleDTO(
                opened_at_ms=1_700_000_000_000,
                open=Decimal("100"),
                high=Decimal("110"),
                low=Decimal("95"),
                close=Decimal("105"),
                volume=Decimal("12"),
                closed=True,
            ),
            OHLCVCandleDTO(
                opened_at_ms=1_700_000_060_000,
                open=Decimal("105"),
                high=Decimal("115"),
                low=Decimal("100"),
                close=Decimal("110"),
                volume=Decimal("8"),
                closed=True,
            ),
        ]
        dto = OHLCVHistoryDTO.from_chunks(
            venue="kucoin",
            symbol="BTC-USDT",
            timeframe="1m",
            range_start_ms=1_700_000_000_000,
            range_end_ms=1_700_000_120_000,
            candles=candles,
            chunks_fetched=2,
            reason_codes=["chunk:0", "chunk:1", "cache:hit"],
        )
        assert dto.chunks_fetched == 2
        assert dto.range_end_ms == 1_700_000_120_000
        assert len(dto.candles) == 2
        assert dto.reason_codes == ["chunk:0", "chunk:1", "cache:hit"]

    def test_serializes_to_json_decimals_as_strings(self) -> None:
        dto = OHLCVHistoryDTO.from_chunks(
            venue="kucoin",
            symbol="BTC-USDT",
            timeframe="1h",
            range_start_ms=0,
            range_end_ms=3_600_000,
            candles=[
                OHLCVCandleDTO(
                    opened_at_ms=0,
                    open=Decimal("1.234"),
                    high=Decimal("2"),
                    low=Decimal("1"),
                    close=Decimal("1.5"),
                    volume=Decimal("0.5"),
                    closed=True,
                ),
            ],
            chunks_fetched=1,
            reason_codes=[],
        )
        payload = dto.model_dump(mode="json")
        assert payload["candles"][0]["open"] == "1.234"
        assert payload["chunks_fetched"] == 1


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


class TestSymbolDTO:
    def test_from_domain_basic_spot_symbol(self) -> None:
        symbol = SymbolRegistry().get(
            VenueId.KUCOIN,
            "BTC",
            "USDT",
            market_type=MarketType.SPOT,
            native_symbol="BTC-USDT",
        )
        dto = SymbolDTO.from_domain(symbol)
        assert dto.venue == "kucoin"
        assert dto.base == "BTC"
        assert dto.quote == "USDT"
        assert dto.native_symbol == "BTC-USDT"
        assert dto.market_type == "spot"

    def test_dto_serializes_to_json(self) -> None:
        symbol = SymbolRegistry().get(
            VenueId.KUCOIN,
            "ETH",
            "USDT",
            market_type=MarketType.SPOT,
            native_symbol="ETH-USDT",
        )
        dto = SymbolDTO.from_domain(symbol)
        payload = dto.model_dump(mode="json")
        assert payload["venue"] == "kucoin"
        assert payload["native_symbol"] == "ETH-USDT"


class TestTrendingAssetDTO:
    def test_from_domain(self) -> None:
        asset = Asset(
            code="BTC",
            name="Bitcoin",
            coingecko_id="bitcoin",
            market_cap_rank=1,
            categories=(AssetCategory.LAYER_1,),
        )
        dto = TrendingAssetDTO.from_domain(asset, rank=0)
        assert dto.code == "BTC"
        assert dto.name == "Bitcoin"
        assert dto.coingecko_id == "bitcoin"
        assert dto.market_cap_rank == 1
        assert dto.categories == ["layer_1"]
        assert dto.rank == 0


class TestCategoryDTO:
    def test_from_dict_core_fields(self) -> None:
        raw = {
            "category_id": "layer-1",
            "name": "Layer 1",
            "market_cap": 1000000000,
            "market_cap_change_24h": 1.5,
        }
        dto = CategoryDTO.from_provider(raw)
        assert dto.id == "layer-1"
        assert dto.name == "Layer 1"
        assert dto.market_cap == Decimal("1000000000")
        assert dto.market_cap_change_24h_pct == Decimal("1.5")

    def test_missing_optional_fields_become_none(self) -> None:
        raw = {"category_id": "meme", "name": "Meme"}
        dto = CategoryDTO.from_provider(raw)
        assert dto.market_cap is None
        assert dto.market_cap_change_24h_pct is None


class TestAnalysisResultDTO:
    def test_from_domain_copies_core_fields(self) -> None:
        result = AnalysisResult(
            strategy="vwap",
            findings={"vwap": Decimal("100.5"), "bars_used": 10},
            confidence=Confidence.HIGH,
        )
        dto = AnalysisResultDTO.from_domain(result, reason_codes=["cache:hit"])
        assert dto.strategy == "vwap"
        assert dto.confidence == "high"
        assert dto.findings == {"vwap": Decimal("100.5"), "bars_used": 10}
        assert dto.reason_codes == ["cache:hit"]

    def test_tuple_findings_become_lists_in_json(self) -> None:
        result = AnalysisResult(
            strategy="support_resistance",
            findings={
                "supports": (Decimal("90"), Decimal("85")),
                "resistances": (Decimal("110"),),
            },
            confidence=Confidence.MEDIUM,
        )
        dto = AnalysisResultDTO.from_domain(result, reason_codes=[])
        payload = dto.model_dump(mode="json")
        assert payload["findings"]["supports"] == ["90", "85"]
        assert payload["findings"]["resistances"] == ["110"]

    def test_none_findings_preserved(self) -> None:
        result = AnalysisResult(
            strategy="volatility_regime",
            findings={"atr": None, "regime": "unknown"},
            confidence=Confidence.LOW,
        )
        dto = AnalysisResultDTO.from_domain(result, reason_codes=[])
        assert dto.findings["atr"] is None
        assert dto.findings["regime"] == "unknown"


class TestAnalysisReportDTO:
    def test_from_domain_carries_all_strategies(self) -> None:
        symbol = SymbolRegistry().get(
            VenueId.KUCOIN,
            "BTC",
            "USDT",
            market_type=MarketType.SPOT,
            native_symbol="BTC-USDT",
        )
        r1 = AnalysisResult(
            strategy="vwap",
            findings={"vwap": Decimal("100")},
            confidence=Confidence.HIGH,
        )
        r2 = AnalysisResult(
            strategy="volatility_regime",
            findings={"regime": "calm"},
            confidence=Confidence.MEDIUM,
        )
        report = AnalysisReport(
            symbol=symbol,
            timeframe=Timeframe.H1,
            results=(r1, r2),
        )
        dto = AnalysisReportDTO.from_domain(
            report,
            reason_codes=["provider:called"],
        )
        assert dto.venue == "kucoin"
        assert dto.symbol == "BTC-USDT"
        assert dto.timeframe == "1h"
        assert len(dto.results) == 2
        assert dto.results[0].strategy == "vwap"
        assert dto.results[1].strategy == "volatility_regime"
        assert dto.reason_codes == ["provider:called"]
