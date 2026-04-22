"""Catalog tools return Pydantic DTOs → clients receive `structuredContent`.

Mirrors `test_resources.py` but invokes via `Client(mcp).call_tool(...)` so
regressions in DTO serialisation (escape-rule issue reported in PR #1 review)
are caught without relying on resource wire format.
"""

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import Client, FastMCP

from cryptozavr.application.services.discovery_service import DiscoveryService
from cryptozavr.domain.assets import Asset, AssetCategory
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.state.venue_state import VenueState
from cryptozavr.mcp.lifespan_state import LIFESPAN_KEYS
from cryptozavr.mcp.tools.catalog import register_catalog_tools


def _build_server(
    *,
    registry: SymbolRegistry | None = None,
    discovery: DiscoveryService | None = None,
    venue_states: dict[VenueId, VenueState] | None = None,
) -> FastMCP:
    state = {
        LIFESPAN_KEYS.registry: registry or SymbolRegistry(),
        LIFESPAN_KEYS.discovery_service: discovery or MagicMock(spec=DiscoveryService),
        LIFESPAN_KEYS.venue_states: venue_states or {},
    }

    @asynccontextmanager
    async def lifespan(_server):
        yield state

    mcp = FastMCP(name="t", version="0", lifespan=lifespan)
    register_catalog_tools(mcp)
    return mcp


def _structured(result) -> dict:
    """Return the tool's structuredContent or a parsed JSON fallback."""
    sc = getattr(result, "structured_content", None)
    if sc is not None:
        return sc
    return json.loads(result.content[0].text)


@pytest.mark.asyncio
async def test_list_venues_returns_sorted_venue_ids() -> None:
    mcp = _build_server()
    async with Client(mcp) as client:
        result = await client.call_tool("list_venues", {})
    payload = _structured(result)
    assert "coingecko" in payload["venues"]
    assert "kucoin" in payload["venues"]
    assert payload["venues"] == sorted(payload["venues"])


@pytest.mark.asyncio
async def test_list_symbols_returns_registered_symbols_for_venue() -> None:
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
    mcp = _build_server(registry=registry)
    async with Client(mcp) as client:
        result = await client.call_tool("list_symbols", {"venue": "kucoin"})
    payload = _structured(result)
    assert payload["venue"] == "kucoin"
    assert payload["error"] is None
    native = {s["native_symbol"] for s in payload["symbols"]}
    assert native == {"BTC-USDT", "ETH-USDT"}


@pytest.mark.asyncio
async def test_list_symbols_unknown_venue_returns_error_field() -> None:
    mcp = _build_server()
    async with Client(mcp) as client:
        result = await client.call_tool("list_symbols", {"venue": "binance"})
    payload = _structured(result)
    assert payload["venue"] == "binance"
    assert payload["symbols"] == []
    assert payload["error"] == "unsupported"


@pytest.mark.asyncio
async def test_list_trending_returns_ranked_assets() -> None:
    discovery = MagicMock(spec=DiscoveryService)
    discovery.list_trending = AsyncMock(
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
    mcp = _build_server(discovery=discovery)
    async with Client(mcp) as client:
        result = await client.call_tool("list_trending", {})
    payload = _structured(result)
    assert payload["error"] is None
    assert [a["rank"] for a in payload["assets"]] == [0, 1]
    assert payload["assets"][0]["code"] == "BTC"


@pytest.mark.asyncio
async def test_list_trending_degrades_with_error_field_on_upstream_failure() -> None:
    discovery = MagicMock(spec=DiscoveryService)
    discovery.list_trending = AsyncMock(side_effect=RuntimeError("coingecko down"))
    mcp = _build_server(discovery=discovery)
    async with Client(mcp) as client:
        result = await client.call_tool("list_trending", {})
    payload = _structured(result)
    assert payload["assets"] == []
    assert "RuntimeError" in (payload["error"] or "")


@pytest.mark.asyncio
async def test_list_categories_maps_provider_rows_to_dto() -> None:
    discovery = MagicMock(spec=DiscoveryService)
    discovery.list_categories = AsyncMock(
        return_value=[
            {
                "category_id": "layer-1",
                "id": "layer-1",
                "name": "Layer 1",
                "market_cap": 1_500_000_000,
                "market_cap_change_24h": 2.1,
            },
            {
                "category_id": "meme",
                "id": "meme",
                "name": "Meme",
                "market_cap": 50_000_000,
                "market_cap_change_24h": -3.0,
            },
        ],
    )
    mcp = _build_server(discovery=discovery)
    async with Client(mcp) as client:
        result = await client.call_tool("list_categories", {})
    payload = _structured(result)
    assert payload["error"] is None
    assert len(payload["categories"]) == 2
    assert payload["categories"][0]["id"] == "layer-1"
    assert payload["categories"][0]["market_cap"] == "1500000000"


@pytest.mark.asyncio
async def test_get_venue_health_reports_state_per_venue() -> None:
    kucoin = VenueState(VenueId.KUCOIN)
    kucoin.mark_probe_performed(1_700_000_000_000)
    states = {
        VenueId.KUCOIN: kucoin,
        VenueId.COINGECKO: VenueState(VenueId.COINGECKO),
    }
    mcp = _build_server(venue_states=states)
    async with Client(mcp) as client:
        result = await client.call_tool("get_venue_health", {})
    payload = _structured(result)
    by_venue = {entry["venue"]: entry for entry in payload["venues"]}
    assert by_venue["kucoin"]["state"] == "healthy"
    assert by_venue["kucoin"]["last_checked_ms"] == 1_700_000_000_000
    assert by_venue["coingecko"]["last_checked_ms"] is None
