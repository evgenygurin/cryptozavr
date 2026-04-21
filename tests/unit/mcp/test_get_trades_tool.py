"""In-memory Client(mcp) tests for the get_trades tool."""

from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from cryptozavr.application.services.trades_service import TradesFetchResult, TradesService
from cryptozavr.domain.exceptions import SymbolNotFoundError
from cryptozavr.domain.market_data import TradeSide, TradeTick
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.mcp.lifespan_state import LIFESPAN_KEYS
from cryptozavr.mcp.tools.trades import register_trades_tool


def _make_trades() -> tuple[TradeTick, ...]:
    symbol = SymbolRegistry().get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )
    return (
        TradeTick(
            symbol=symbol,
            price=Decimal("100.5"),
            size=Decimal("0.1"),
            side=TradeSide.BUY,
            executed_at=Instant.from_ms(1_700_000_000_000),
            trade_id="t1",
        ),
    )


def _build_server(mock_service) -> FastMCP:
    @asynccontextmanager
    async def lifespan(server):
        yield {LIFESPAN_KEYS.trades_service: mock_service}

    mcp = FastMCP(name="test", version="0.0.0", lifespan=lifespan)
    register_trades_tool(mcp)
    return mcp


@pytest.mark.asyncio
async def test_get_trades_returns_dto_fields() -> None:
    # Use spec= so MagicMock is not treated as AbstractAsyncContextManager
    # by FastMCP's Depends() resolution engine.
    service = MagicMock(spec=TradesService)
    service.fetch_trades = AsyncMock(
        return_value=TradesFetchResult(
            venue="kucoin",
            symbol="BTC-USDT",
            trades=_make_trades(),
            reason_codes=["venue:healthy", "cache:miss", "provider:called"],
        ),
    )
    mcp = _build_server(service)
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_trades",
            {"venue": "kucoin", "symbol": "BTC-USDT", "limit": 100},
        )
    payload = result.structured_content
    assert payload["venue"] == "kucoin"
    assert payload["symbol"] == "BTC-USDT"
    assert len(payload["trades"]) == 1
    assert payload["trades"][0]["side"] == "buy"
    assert payload["trades"][0]["trade_id"] == "t1"
    assert "provider:called" in payload["reason_codes"]
    call_kwargs = service.fetch_trades.call_args.kwargs
    assert call_kwargs["venue"] == "kucoin"
    assert call_kwargs["symbol"] == "BTC-USDT"
    assert call_kwargs["limit"] == 100
    assert call_kwargs["force_refresh"] is False


@pytest.mark.asyncio
async def test_get_trades_forwards_force_refresh() -> None:
    service = MagicMock(spec=TradesService)
    service.fetch_trades = AsyncMock(
        return_value=TradesFetchResult(
            venue="kucoin",
            symbol="BTC-USDT",
            trades=(),
            reason_codes=["cache:bypassed"],
        ),
    )
    mcp = _build_server(service)
    async with Client(mcp) as client:
        await client.call_tool(
            "get_trades",
            {
                "venue": "kucoin",
                "symbol": "BTC-USDT",
                "limit": 50,
                "force_refresh": True,
            },
        )
    call_kwargs = service.fetch_trades.call_args.kwargs
    assert call_kwargs["limit"] == 50
    assert call_kwargs["force_refresh"] is True


@pytest.mark.asyncio
async def test_get_trades_symbol_not_found_surfaces_tool_error() -> None:
    service = MagicMock(spec=TradesService)
    service.fetch_trades = AsyncMock(
        side_effect=SymbolNotFoundError(
            user_input="DOGE-USDT",
            venue="kucoin",
        ),
    )
    mcp = _build_server(service)
    async with Client(mcp) as client:
        with pytest.raises(ToolError) as exc_info:
            await client.call_tool(
                "get_trades",
                {"venue": "kucoin", "symbol": "DOGE-USDT", "limit": 100},
            )
    assert "DOGE-USDT" in str(exc_info.value)
