"""Test cryptozavr resources."""

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import Client, FastMCP

from cryptozavr.application.services.discovery_service import DiscoveryService
from cryptozavr.domain.assets import Asset, AssetCategory
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.mcp.lifespan_state import LIFESPAN_KEYS
from cryptozavr.mcp.resources.catalogs import register_resources


def _build_server(registry: SymbolRegistry) -> FastMCP:
    @asynccontextmanager
    async def lifespan(_server):
        yield {LIFESPAN_KEYS.registry: registry}

    mcp = FastMCP(name="t", version="0", lifespan=lifespan)
    register_resources(mcp)
    return mcp


def _build_discovery_server(discovery_service: DiscoveryService) -> FastMCP:
    @asynccontextmanager
    async def lifespan(_server):
        yield {
            LIFESPAN_KEYS.registry: SymbolRegistry(),
            LIFESPAN_KEYS.discovery_service: discovery_service,
        }

    mcp = FastMCP(name="t", version="0", lifespan=lifespan)
    register_resources(mcp)
    return mcp


@pytest.mark.asyncio
async def test_venues_resource_lists_supported() -> None:
    mcp = _build_server(SymbolRegistry())
    async with Client(mcp) as client:
        result = await client.read_resource("cryptozavr://venues")
    payload = json.loads(result[0].text)
    assert "kucoin" in payload["venues"]
    assert "coingecko" in payload["venues"]


@pytest.mark.asyncio
async def test_symbols_resource_by_venue() -> None:
    registry = SymbolRegistry()
    registry.get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )
    registry.get(
        VenueId.KUCOIN,
        "ETH",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="ETH-USDT",
    )
    mcp = _build_server(registry)
    async with Client(mcp) as client:
        result = await client.read_resource("cryptozavr://symbols/kucoin")
    payload = json.loads(result[0].text)
    assert payload["venue"] == "kucoin"
    native = {s["native_symbol"] for s in payload["symbols"]}
    assert native == {"BTC-USDT", "ETH-USDT"}


@pytest.mark.asyncio
async def test_symbols_resource_unknown_venue_returns_error_payload() -> None:
    mcp = _build_server(SymbolRegistry())
    async with Client(mcp) as client:
        result = await client.read_resource("cryptozavr://symbols/binance")
    payload = json.loads(result[0].text)
    assert payload["venue"] == "binance"
    assert payload["symbols"] == []
    assert payload.get("error") == "unsupported"


@pytest.mark.asyncio
async def test_trending_resource_returns_ranked_list() -> None:
    service = MagicMock(spec=DiscoveryService)
    service.list_trending = AsyncMock(
        return_value=[
            Asset(
                code="BTC",
                name="Bitcoin",
                coingecko_id="bitcoin",
                market_cap_rank=1,
                categories=(AssetCategory.LAYER_1,),
            ),
            Asset(
                code="PEPE",
                name="Pepe",
                coingecko_id="pepe",
                market_cap_rank=30,
                categories=(AssetCategory.MEME,),
            ),
        ],
    )
    mcp = _build_discovery_server(service)
    async with Client(mcp) as client:
        result = await client.read_resource("cryptozavr://trending")
    payload = json.loads(result[0].text)
    assert len(payload["assets"]) == 2
    assert payload["assets"][0]["code"] == "BTC"
    assert payload["assets"][0]["rank"] == 0
    assert payload["assets"][1]["rank"] == 1


@pytest.mark.asyncio
async def test_categories_resource_returns_list() -> None:
    service = MagicMock(spec=DiscoveryService)
    service.list_categories = AsyncMock(
        return_value=[
            {
                "category_id": "layer-1",
                "name": "Layer 1",
                "market_cap": 1_500_000_000,
                "market_cap_change_24h": 2.0,
            },
            {
                "category_id": "meme",
                "name": "Meme",
                "market_cap": 50_000_000,
                "market_cap_change_24h": -3.0,
            },
        ],
    )
    mcp = _build_discovery_server(service)
    async with Client(mcp) as client:
        result = await client.read_resource("cryptozavr://categories")
    payload = json.loads(result[0].text)
    assert len(payload["categories"]) == 2
    assert payload["categories"][0]["id"] == "layer-1"
    assert payload["categories"][0]["market_cap"] == "1500000000"


@pytest.mark.asyncio
async def test_trending_resource_empty_on_service_failure() -> None:
    # When service raises, resource returns empty payload (not tool error)
    service = MagicMock(spec=DiscoveryService)
    service.list_trending = AsyncMock(side_effect=RuntimeError("upstream down"))
    mcp = _build_discovery_server(service)
    async with Client(mcp) as client:
        result = await client.read_resource("cryptozavr://trending")
    payload = json.loads(result[0].text)
    assert payload["assets"] == []
    assert "error" in payload
