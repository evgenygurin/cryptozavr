"""Test CCXTProvider with fake exchange (no network)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import ccxt.async_support as ccxt_async
import pytest

from cryptozavr.domain.exceptions import (
    ProviderUnavailableError,
    RateLimitExceededError,
)
from cryptozavr.domain.market_data import TradeSide
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Timeframe
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.ccxt_provider import CCXTProvider
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

FIXTURE_DIR = Path(__file__).resolve().parents[3] / "contract" / "fixtures" / "kucoin"


class _FakeExchange:
    """Minimal CCXT exchange duck-type for tests."""

    def __init__(
        self,
        *,
        ticker: dict | None = None,
        ohlcv: list | None = None,
        order_book: dict | None = None,
        trades: list | None = None,
        load_markets_raises: Exception | None = None,
        ticker_raises: Exception | None = None,
    ) -> None:
        self._ticker = ticker
        self._ohlcv = ohlcv
        self._order_book = order_book
        self._trades = trades
        self._load_markets_raises = load_markets_raises
        self._ticker_raises = ticker_raises
        self.load_markets_called = 0
        self.closed = False
        self.last_order_book_limit: int | None = None
        self.last_trades_args: tuple[str, int | None, int] | None = None

    async def load_markets(self) -> dict:
        self.load_markets_called += 1
        if self._load_markets_raises:
            raise self._load_markets_raises
        return {}

    async def fetch_ticker(self, symbol: str) -> dict:
        if self._ticker_raises:
            raise self._ticker_raises
        assert self._ticker is not None
        return self._ticker

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: int | None = None,
        limit: int = 500,
    ) -> list:
        assert self._ohlcv is not None
        return self._ohlcv

    async def fetch_order_book(self, symbol: str, limit: int = 50) -> dict:
        assert self._order_book is not None
        self.last_order_book_limit = limit
        return self._order_book

    async def fetch_trades(
        self,
        symbol: str,
        since: int | None = None,
        limit: int = 100,
    ) -> list:
        assert self._trades is not None
        self.last_trades_args = (symbol, since, limit)
        return self._trades

    async def close(self) -> None:
        self.closed = True


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
def ticker_fix() -> dict:
    return json.loads((FIXTURE_DIR / "fetch_ticker_btc_usdt.json").read_text())


@pytest.fixture
def ohlcv_fix() -> list:
    return json.loads((FIXTURE_DIR / "fetch_ohlcv_btc_usdt_1h.json").read_text())


@pytest.fixture
def ob_fix() -> dict:
    return json.loads((FIXTURE_DIR / "fetch_order_book_btc_usdt.json").read_text())


@pytest.mark.asyncio
async def test_fetch_ticker_happy_path(btc_symbol, ticker_fix: dict) -> None:
    fake = _FakeExchange(ticker=ticker_fix)
    provider = CCXTProvider(
        venue_id=VenueId.KUCOIN,
        state=VenueState(VenueId.KUCOIN),
        exchange=fake,
    )
    ticker = await provider.fetch_ticker(btc_symbol)
    assert ticker.last == Decimal("65000.5")
    assert fake.load_markets_called == 1


@pytest.mark.asyncio
async def test_fetch_ohlcv_happy_path(btc_symbol, ohlcv_fix: list) -> None:
    fake = _FakeExchange(ohlcv=ohlcv_fix)
    provider = CCXTProvider(
        venue_id=VenueId.KUCOIN,
        state=VenueState(VenueId.KUCOIN),
        exchange=fake,
    )
    series = await provider.fetch_ohlcv(btc_symbol, Timeframe.H1, limit=5)
    assert len(series.candles) == 5


@pytest.mark.asyncio
async def test_fetch_order_book_happy_path(btc_symbol, ob_fix: dict) -> None:
    fake = _FakeExchange(order_book=ob_fix)
    provider = CCXTProvider(
        venue_id=VenueId.KUCOIN,
        state=VenueState(VenueId.KUCOIN),
        exchange=fake,
    )
    ob = await provider.fetch_order_book(btc_symbol, depth=3)
    assert len(ob.bids) == 3
    assert len(ob.asks) == 3


@pytest.mark.asyncio
async def test_rate_limit_exception_translated(btc_symbol) -> None:
    fake = _FakeExchange(
        ticker_raises=ccxt_async.RateLimitExceeded("429 Too Many Requests"),
    )
    provider = CCXTProvider(
        venue_id=VenueId.KUCOIN,
        state=VenueState(VenueId.KUCOIN),
        exchange=fake,
    )
    with pytest.raises(RateLimitExceededError):
        await provider.fetch_ticker(btc_symbol)


@pytest.mark.asyncio
async def test_network_exception_translated(btc_symbol) -> None:
    fake = _FakeExchange(
        ticker_raises=ccxt_async.NetworkError("connection refused"),
    )
    provider = CCXTProvider(
        venue_id=VenueId.KUCOIN,
        state=VenueState(VenueId.KUCOIN),
        exchange=fake,
    )
    with pytest.raises(ProviderUnavailableError):
        await provider.fetch_ticker(btc_symbol)


@pytest.mark.asyncio
async def test_close_closes_exchange(btc_symbol, ticker_fix: dict) -> None:
    fake = _FakeExchange(ticker=ticker_fix)
    provider = CCXTProvider(
        venue_id=VenueId.KUCOIN,
        state=VenueState(VenueId.KUCOIN),
        exchange=fake,
    )
    await provider.close()
    assert fake.closed is True


@pytest.mark.asyncio
async def test_markets_loaded_only_once(btc_symbol, ticker_fix: dict) -> None:
    fake = _FakeExchange(ticker=ticker_fix)
    provider = CCXTProvider(
        venue_id=VenueId.KUCOIN,
        state=VenueState(VenueId.KUCOIN),
        exchange=fake,
    )
    await provider.fetch_ticker(btc_symbol)
    await provider.fetch_ticker(btc_symbol)
    await provider.fetch_ticker(btc_symbol)
    assert fake.load_markets_called == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("requested", "expected_limit"),
    [(1, 20), (15, 20), (20, 20), (21, 100), (50, 100), (200, 100)],
)
async def test_order_book_depth_snapped_for_kucoin(
    btc_symbol,
    ob_fix: dict,
    requested: int,
    expected_limit: int,
) -> None:
    fake = _FakeExchange(order_book=ob_fix)
    provider = CCXTProvider(
        venue_id=VenueId.KUCOIN,
        state=VenueState(VenueId.KUCOIN),
        exchange=fake,
    )
    await provider.fetch_order_book(btc_symbol, depth=requested)
    assert fake.last_order_book_limit == expected_limit


@pytest.mark.asyncio
async def test_fetch_trades_happy_path(btc_symbol) -> None:
    raw = [
        {
            "id": "t1",
            "timestamp": 1_700_000_000_000,
            "side": "buy",
            "price": 65000.5,
            "amount": 0.01,
        },
        {
            "id": "t2",
            "timestamp": 1_700_000_001_000,
            "side": "sell",
            "price": 65001.0,
            "amount": 0.02,
        },
    ]
    fake = _FakeExchange(trades=raw)
    provider = CCXTProvider(
        venue_id=VenueId.KUCOIN,
        state=VenueState(VenueId.KUCOIN),
        exchange=fake,
    )

    trades = await provider.fetch_trades(btc_symbol, limit=5)

    assert len(trades) == 2
    assert trades[0].side is TradeSide.BUY
    assert trades[1].side is TradeSide.SELL
    assert trades[0].price == Decimal("65000.5")
    assert trades[0].size == Decimal("0.01")
    assert trades[0].trade_id == "t1"
    assert fake.last_trades_args == ("BTC-USDT", None, 5)


@pytest.mark.asyncio
async def test_fetch_trades_forwards_since_as_ms(btc_symbol) -> None:
    """`since: Instant` must be converted to int ms before hitting CCXT."""

    raw = [
        {
            "id": "t1",
            "timestamp": 1_700_000_000_000,
            "side": "buy",
            "price": 1.0,
            "amount": 1.0,
        }
    ]
    fake = _FakeExchange(trades=raw)
    provider = CCXTProvider(
        venue_id=VenueId.KUCOIN,
        state=VenueState(VenueId.KUCOIN),
        exchange=fake,
    )
    await provider.fetch_trades(btc_symbol, since=Instant.from_ms(1_699_900_000_000), limit=5)
    assert fake.last_trades_args == ("BTC-USDT", 1_699_900_000_000, 5)


@pytest.mark.asyncio
async def test_fetch_trades_unknown_side_falls_back(btc_symbol) -> None:
    raw = [
        {
            "id": "t1",
            "timestamp": 0,
            "side": "weird",
            "price": 1.0,
            "amount": 1.0,
        },
    ]
    fake = _FakeExchange(trades=raw)
    provider = CCXTProvider(
        venue_id=VenueId.KUCOIN,
        state=VenueState(VenueId.KUCOIN),
        exchange=fake,
    )
    trades = await provider.fetch_trades(btc_symbol, limit=1)
    assert trades[0].side is TradeSide.UNKNOWN
