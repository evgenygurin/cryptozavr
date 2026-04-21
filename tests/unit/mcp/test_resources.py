"""Test cryptozavr resources."""

import json
from contextlib import asynccontextmanager

import pytest
from fastmcp import Client, FastMCP

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
