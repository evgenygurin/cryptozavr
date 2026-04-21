"""Contract tests: CCXTProvider against saved KuCoin fixtures.

Marker: @pytest.mark.contract. Runs without network.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.ccxt_provider import CCXTProvider
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

pytestmark = pytest.mark.contract

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "kucoin"


class _FakeKucoin:
    """Replays saved fixtures as if they were live CCXT responses."""

    def __init__(self) -> None:
        self._ticker = json.loads((FIXTURE_DIR / "fetch_ticker_btc_usdt.json").read_text())
        self._ohlcv = json.loads((FIXTURE_DIR / "fetch_ohlcv_btc_usdt_1h.json").read_text())
        self._ob = json.loads((FIXTURE_DIR / "fetch_order_book_btc_usdt.json").read_text())

    async def load_markets(self) -> dict:
        return {}

    async def fetch_ticker(self, symbol: str) -> dict:
        return self._ticker

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: int | None = None,
        limit: int = 500,
    ) -> list:
        return self._ohlcv

    async def fetch_order_book(self, symbol: str, limit: int = 50) -> dict:
        return self._ob

    async def close(self) -> None:
        return None


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
def kucoin_provider(btc_symbol) -> CCXTProvider:
    return CCXTProvider(
        venue_id=VenueId.KUCOIN,
        state=VenueState(VenueId.KUCOIN),
        exchange=_FakeKucoin(),
    )


async def test_full_ticker_path(kucoin_provider: CCXTProvider, btc_symbol) -> None:
    ticker = await kucoin_provider.fetch_ticker(btc_symbol)
    assert ticker.last == Decimal("65000.5")
    assert ticker.quality.source.venue_id == "kucoin"


async def test_full_ohlcv_path(kucoin_provider: CCXTProvider, btc_symbol) -> None:
    series = await kucoin_provider.fetch_ohlcv(
        btc_symbol,
        Timeframe.H1,
        limit=5,
    )
    assert len(series.candles) == 5
    assert series.candles[0].open == Decimal("64000.0")
    assert series.candles[-1].close == Decimal("65200.0")


async def test_full_orderbook_path(kucoin_provider: CCXTProvider, btc_symbol) -> None:
    ob = await kucoin_provider.fetch_order_book(btc_symbol, depth=3)
    assert ob.best_bid() is not None
    assert ob.best_ask() is not None
    spread = ob.spread()
    assert spread is not None
    assert spread == Decimal("2.0")
