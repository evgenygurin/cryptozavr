"""In-memory Client tests for resolve_symbol tool."""

from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from cryptozavr.application.services.symbol_resolver import SymbolResolver
from cryptozavr.domain.exceptions import SymbolNotFoundError
from cryptozavr.domain.symbols import Symbol, SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.mcp.lifespan_state import LIFESPAN_KEYS
from cryptozavr.mcp.tools.discovery import register_resolve_symbol_tool


def _btc() -> Symbol:
    return SymbolRegistry().get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )


def _build_server(resolver: SymbolResolver) -> FastMCP:
    @asynccontextmanager
    async def lifespan(_server):
        yield {LIFESPAN_KEYS.symbol_resolver: resolver}

    mcp = FastMCP(name="t", version="0", lifespan=lifespan)
    register_resolve_symbol_tool(mcp)
    return mcp


@pytest.mark.asyncio
async def test_resolve_symbol_returns_dto() -> None:
    resolver = MagicMock(spec=SymbolResolver)
    resolver.resolve = MagicMock(return_value=_btc())
    mcp = _build_server(resolver)
    async with Client(mcp) as client:
        result = await client.call_tool(
            "resolve_symbol",
            {"user_input": "btc", "venue": "kucoin"},
        )
    payload = result.structured_content
    assert payload["native_symbol"] == "BTC-USDT"
    assert payload["base"] == "BTC"
    assert payload["quote"] == "USDT"
    assert payload["venue"] == "kucoin"
    resolver.resolve.assert_called_once_with(
        user_input="btc",
        venue="kucoin",
    )


@pytest.mark.asyncio
async def test_resolve_symbol_not_found_surfaces_tool_error() -> None:
    resolver = MagicMock(spec=SymbolResolver)
    resolver.resolve = MagicMock(
        side_effect=SymbolNotFoundError(user_input="DOGE", venue="kucoin"),
    )
    mcp = _build_server(resolver)
    async with Client(mcp) as client:
        with pytest.raises(ToolError) as exc_info:
            await client.call_tool(
                "resolve_symbol",
                {"user_input": "DOGE", "venue": "kucoin"},
            )
    assert "DOGE" in str(exc_info.value)
