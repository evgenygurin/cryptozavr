"""Test CoinGeckoProvider with respx-mocked httpx."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from cryptozavr.domain.exceptions import (
    ProviderUnavailableError,
    RateLimitExceededError,
)
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.coingecko_provider import (
    CoinGeckoProvider,
)
from cryptozavr.infrastructure.providers.http import HttpClientRegistry
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

FIXTURE_DIR = Path(__file__).resolve().parents[3] / "contract" / "fixtures" / "coingecko"
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


async def _build_provider() -> tuple[CoinGeckoProvider, HttpClientRegistry]:
    reg = HttpClientRegistry()
    client = await reg.get("coingecko", base_url=BASE_URL)
    provider = CoinGeckoProvider(
        state=VenueState(VenueId.COINGECKO),
        client=client,
    )
    return provider, reg


@pytest.mark.asyncio
@respx.mock
async def test_fetch_ticker_happy_path(btc_symbol) -> None:
    raw = json.loads((FIXTURE_DIR / "simple_price_btc.json").read_text())
    respx.get(f"{BASE_URL}/simple/price").mock(
        return_value=httpx.Response(200, json=raw),
    )
    provider, reg = await _build_provider()
    try:
        ticker = await provider.fetch_ticker(btc_symbol)
        assert ticker.last == Decimal("65000.5")
        assert ticker.quality.source.venue_id == "coingecko"
    finally:
        await reg.close_all()


@pytest.mark.asyncio
@respx.mock
async def test_list_trending_returns_assets() -> None:
    raw = json.loads((FIXTURE_DIR / "trending.json").read_text())
    respx.get(f"{BASE_URL}/search/trending").mock(
        return_value=httpx.Response(200, json=raw),
    )
    provider, reg = await _build_provider()
    try:
        assets = await provider.list_trending(limit=15)
        assert len(assets) == 3
        assert assets[0].code == "BTC"
    finally:
        await reg.close_all()


@pytest.mark.asyncio
@respx.mock
async def test_list_categories_returns_list() -> None:
    raw = json.loads((FIXTURE_DIR / "categories.json").read_text())
    respx.get(f"{BASE_URL}/coins/categories").mock(
        return_value=httpx.Response(200, json=raw),
    )
    provider, reg = await _build_provider()
    try:
        cats = await provider.list_categories(limit=30)
        assert len(cats) == 3
        assert cats[0]["id"] == "layer-1"
    finally:
        await reg.close_all()


@pytest.mark.asyncio
@respx.mock
async def test_rate_limit_translated(btc_symbol) -> None:
    respx.get(f"{BASE_URL}/simple/price").mock(
        return_value=httpx.Response(429, json={"error": "rate limit"}),
    )
    provider, reg = await _build_provider()
    try:
        with pytest.raises(RateLimitExceededError):
            await provider.fetch_ticker(btc_symbol)
    finally:
        await reg.close_all()


@pytest.mark.asyncio
@respx.mock
async def test_network_error_translated(btc_symbol) -> None:
    respx.get(f"{BASE_URL}/simple/price").mock(
        side_effect=httpx.ConnectError("connection refused"),
    )
    provider, reg = await _build_provider()
    try:
        with pytest.raises(ProviderUnavailableError):
            await provider.fetch_ticker(btc_symbol)
    finally:
        await reg.close_all()


@pytest.mark.asyncio
async def test_load_markets_is_noop() -> None:
    provider, reg = await _build_provider()
    try:
        await provider.load_markets()  # no raise
    finally:
        await reg.close_all()
