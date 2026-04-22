"""Test CCXTAdapter pure functions on saved unified-format fixtures."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from cryptozavr.domain.market_data import TradeSide
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Timeframe
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.adapters.ccxt_adapter import CCXTAdapter

FIXTURE_DIR = Path(__file__).resolve().parents[4] / "contract" / "fixtures" / "kucoin"


@pytest.fixture
def registry() -> SymbolRegistry:
    return SymbolRegistry()


@pytest.fixture
def btc_symbol(registry: SymbolRegistry):
    return registry.get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )


@pytest.fixture
def ticker_raw() -> dict:
    return json.loads((FIXTURE_DIR / "fetch_ticker_btc_usdt.json").read_text())


@pytest.fixture
def ohlcv_raw() -> list:
    return json.loads((FIXTURE_DIR / "fetch_ohlcv_btc_usdt_1h.json").read_text())


@pytest.fixture
def orderbook_raw() -> dict:
    return json.loads((FIXTURE_DIR / "fetch_order_book_btc_usdt.json").read_text())


class TestTickerToDomain:
    def test_happy_path(self, btc_symbol, ticker_raw: dict) -> None:
        ticker = CCXTAdapter.ticker_to_domain(ticker_raw, btc_symbol)
        assert ticker.symbol is btc_symbol
        assert ticker.last == Decimal("65000.5")
        assert ticker.bid == Decimal("64999.5")
        assert ticker.ask == Decimal("65001.5")
        assert ticker.volume_24h == Decimal("1234.56")
        assert ticker.high_24h == Decimal("66000.0")
        assert ticker.low_24h == Decimal("64000.0")
        assert ticker.change_24h_pct is not None
        assert ticker.change_24h_pct.value == Decimal("2.524")
        assert ticker.observed_at == Instant.from_ms(1_745_200_800_000)
        assert ticker.quality.source.venue_id == "kucoin"
        assert ticker.quality.source.endpoint == "fetch_ticker"

    def test_missing_bid_ask_returns_none(self, btc_symbol) -> None:
        partial = {
            "symbol": "BTC/USDT",
            "timestamp": 1745200800000,
            "last": 65000.5,
        }
        ticker = CCXTAdapter.ticker_to_domain(partial, btc_symbol)
        assert ticker.bid is None
        assert ticker.ask is None


class TestOhlcvToSeries:
    def test_happy_path(self, btc_symbol, ohlcv_raw: list) -> None:
        series = CCXTAdapter.ohlcv_to_series(
            ohlcv_raw,
            btc_symbol,
            Timeframe.H1,
        )
        assert len(series.candles) == 5
        assert series.symbol is btc_symbol
        assert series.timeframe == Timeframe.H1
        first = series.candles[0]
        assert first.opened_at == Instant.from_ms(1_745_200_800_000)
        assert first.open == Decimal("64000.0")
        assert first.high == Decimal("64500.0")
        assert first.low == Decimal("63900.0")
        assert first.close == Decimal("64200.0")
        assert first.volume == Decimal("120.5")

    def test_empty_list_raises(self, btc_symbol) -> None:
        with pytest.raises(ValueError, match="empty"):
            CCXTAdapter.ohlcv_to_series([], btc_symbol, Timeframe.H1)


class TestOrderBookToDomain:
    def test_happy_path(self, btc_symbol, orderbook_raw: dict) -> None:
        ob = CCXTAdapter.orderbook_to_domain(orderbook_raw, btc_symbol)
        assert len(ob.bids) == 3
        assert len(ob.asks) == 3
        assert ob.bids[0].price == Decimal("64999.5")
        assert ob.bids[0].size == Decimal("1.0")
        assert ob.asks[0].price == Decimal("65001.5")
        assert ob.asks[0].size == Decimal("0.5")
        assert ob.observed_at == Instant.from_ms(1_745_200_800_000)


class TestTradesToDomain:
    def test_happy_path(self, btc_symbol) -> None:
        raw = [
            {
                "id": "t1",
                "timestamp": 1_745_200_800_000,
                "side": "buy",
                "price": 65000.5,
                "amount": 0.01,
            },
            {
                "id": "t2",
                "timestamp": 1_745_200_801_000,
                "side": "sell",
                "price": 65001.0,
                "amount": 0.02,
            },
        ]
        trades = CCXTAdapter.trades_to_domain(raw, btc_symbol)
        assert len(trades) == 2
        assert trades[0].symbol is btc_symbol
        assert trades[0].price == Decimal("65000.5")
        assert trades[0].size == Decimal("0.01")
        assert trades[0].side is TradeSide.BUY
        assert trades[0].trade_id == "t1"
        assert trades[0].executed_at == Instant.from_ms(1_745_200_800_000)
        assert trades[1].side is TradeSide.SELL

    def test_unknown_side_maps_to_unknown(self, btc_symbol) -> None:
        raw = [
            {
                "id": 42,  # non-string id should still work
                "timestamp": 1_745_200_800_000,
                "side": "???",
                "price": "1.5",
                "amount": "2",
            },
        ]
        trades = CCXTAdapter.trades_to_domain(raw, btc_symbol)
        assert trades[0].side is TradeSide.UNKNOWN
        assert trades[0].trade_id == "42"

    def test_missing_timestamp_falls_back_to_now(self, btc_symbol) -> None:
        raw = [
            {
                "id": None,
                "timestamp": 0,
                "side": "buy",
                "price": 1,
                "amount": 1,
            },
        ]
        trades = CCXTAdapter.trades_to_domain(raw, btc_symbol)
        assert trades[0].trade_id is None
        # executed_at falls back to Instant.now() — just assert positive ms.
        assert trades[0].executed_at.to_ms() > 0

    def test_empty_list_returns_empty_tuple(self, btc_symbol) -> None:
        assert CCXTAdapter.trades_to_domain([], btc_symbol) == ()
