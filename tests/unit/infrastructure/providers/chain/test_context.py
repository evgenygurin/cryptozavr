"""Test FetchRequest/FetchContext/FetchOperation dataclasses."""

from __future__ import annotations

import pytest

from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.chain.context import (
    FetchContext,
    FetchOperation,
    FetchRequest,
)


@pytest.fixture
def btc_symbol():
    return SymbolRegistry().get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )


class TestFetchOperation:
    def test_values(self) -> None:
        assert FetchOperation.TICKER.value == "ticker"
        assert FetchOperation.OHLCV.value == "ohlcv"
        assert FetchOperation.ORDER_BOOK.value == "order_book"
        assert FetchOperation.TRADES.value == "trades"


class TestFetchRequest:
    def test_ticker_request(self, btc_symbol) -> None:
        req = FetchRequest(
            operation=FetchOperation.TICKER,
            symbol=btc_symbol,
        )
        assert req.operation == FetchOperation.TICKER
        assert req.symbol is btc_symbol
        assert req.timeframe is None
        assert req.limit == 500
        assert req.force_refresh is False

    def test_ohlcv_request_with_timeframe(self, btc_symbol) -> None:
        req = FetchRequest(
            operation=FetchOperation.OHLCV,
            symbol=btc_symbol,
            timeframe=Timeframe.H1,
            limit=100,
            force_refresh=True,
        )
        assert req.timeframe == Timeframe.H1
        assert req.limit == 100
        assert req.force_refresh is True


class TestFetchContext:
    def test_empty_context(self, btc_symbol) -> None:
        req = FetchRequest(operation=FetchOperation.TICKER, symbol=btc_symbol)
        ctx = FetchContext(request=req)
        assert ctx.reason_codes == []
        assert ctx.metadata == {}

    def test_add_reason_code(self, btc_symbol) -> None:
        req = FetchRequest(operation=FetchOperation.TICKER, symbol=btc_symbol)
        ctx = FetchContext(request=req)
        ctx.add_reason("venue:healthy")
        ctx.add_reason("cache:miss")
        assert ctx.reason_codes == ["venue:healthy", "cache:miss"]

    def test_has_result(self, btc_symbol) -> None:
        req = FetchRequest(operation=FetchOperation.TICKER, symbol=btc_symbol)
        ctx = FetchContext(request=req)
        assert ctx.has_result() is False
        ctx.metadata["result"] = "some-ticker"
        assert ctx.has_result() is True
