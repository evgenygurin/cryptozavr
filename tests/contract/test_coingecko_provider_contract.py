"""Contract tests: CoinGeckoProvider against saved fixtures via respx."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.coingecko_provider import (
    CoinGeckoProvider,
)
from cryptozavr.infrastructure.providers.http import HttpClientRegistry
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

pytestmark = pytest.mark.contract

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "coingecko"
BASE_URL = "https://api.coingecko.com/api/v3"


@pytest.fixture
def registry() -> SymbolRegistry:
    return SymbolRegistry()


@pytest.fixture
def btc_symbol(registry: SymbolRegistry):
    return registry.get(
        VenueId.COINGECKO,
        "BTC",
        "USD",
        market_type=MarketType.SPOT,
        native_symbol="bitcoin",
    )


@respx.mock
async def test_full_ticker_path(btc_symbol) -> None:
    raw = json.loads((FIXTURE_DIR / "simple_price_btc.json").read_text())
    respx.get(f"{BASE_URL}/simple/price").mock(
        return_value=httpx.Response(200, json=raw),
    )
    reg = HttpClientRegistry()
    try:
        client = await reg.get("coingecko", base_url=BASE_URL)
        provider = CoinGeckoProvider(
            state=VenueState(VenueId.COINGECKO),
            client=client,
        )
        ticker = await provider.fetch_ticker(btc_symbol)
        assert ticker.last == Decimal("65000.5")
    finally:
        await reg.close_all()


@respx.mock
async def test_full_trending_path() -> None:
    raw = json.loads((FIXTURE_DIR / "trending.json").read_text())
    respx.get(f"{BASE_URL}/search/trending").mock(
        return_value=httpx.Response(200, json=raw),
    )
    reg = HttpClientRegistry()
    try:
        client = await reg.get("coingecko", base_url=BASE_URL)
        provider = CoinGeckoProvider(
            state=VenueState(VenueId.COINGECKO),
            client=client,
        )
        assets = await provider.list_trending(limit=2)
        assert len(assets) == 2
        assert assets[0].code == "BTC"
    finally:
        await reg.close_all()
