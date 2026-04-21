"""In-memory Client(mcp) tests for the get_order_book tool."""

from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from cryptozavr.application.services.order_book_service import (
    OrderBookFetchResult,
    OrderBookService,
)
from cryptozavr.domain.exceptions import SymbolNotFoundError
from cryptozavr.domain.market_data import OrderBookSnapshot
from cryptozavr.domain.quality import (
    Confidence,
    DataQuality,
    Provenance,
    Staleness,
)
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, PriceSize
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.mcp.lifespan_state import LIFESPAN_KEYS
from cryptozavr.mcp.tools.order_book import register_order_book_tool


def _make_snapshot() -> OrderBookSnapshot:
    symbol = SymbolRegistry().get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )
    return OrderBookSnapshot(
        symbol=symbol,
        bids=(PriceSize(price=Decimal("100"), size=Decimal("1")),),
        asks=(PriceSize(price=Decimal("101"), size=Decimal("1")),),
        observed_at=Instant.from_ms(1_700_000_000_000),
        quality=DataQuality(
            source=Provenance(
                venue_id="kucoin",
                endpoint="fetch_order_book",
            ),
            fetched_at=Instant.from_ms(1_700_000_000_000),
            staleness=Staleness.FRESH,
            confidence=Confidence.HIGH,
            cache_hit=False,
        ),
    )


def _build_server(mock_service) -> FastMCP:
    @asynccontextmanager
    async def lifespan(server):
        yield {LIFESPAN_KEYS.order_book_service: mock_service}

    mcp = FastMCP(name="test", version="0.0.0", lifespan=lifespan)
    register_order_book_tool(mcp)
    return mcp


@pytest.mark.asyncio
async def test_get_order_book_returns_dto_fields() -> None:
    # Use spec= so MagicMock is not treated as AbstractAsyncContextManager
    # by FastMCP's Depends() resolution engine.
    service = MagicMock(spec=OrderBookService)
    service.fetch_order_book = AsyncMock(
        return_value=OrderBookFetchResult(
            snapshot=_make_snapshot(),
            reason_codes=["venue:healthy", "cache:miss", "provider:called"],
        ),
    )
    mcp = _build_server(service)
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_order_book",
            {"venue": "kucoin", "symbol": "BTC-USDT", "depth": 50},
        )
    payload = result.structured_content
    assert payload["venue"] == "kucoin"
    assert payload["symbol"] == "BTC-USDT"
    assert len(payload["bids"]) == 1
    assert len(payload["asks"]) == 1
    assert payload["spread"] == "1"
    assert "provider:called" in payload["reason_codes"]
    call_kwargs = service.fetch_order_book.call_args.kwargs
    assert call_kwargs["depth"] == 50


@pytest.mark.asyncio
async def test_get_order_book_forwards_force_refresh() -> None:
    service = MagicMock(spec=OrderBookService)
    service.fetch_order_book = AsyncMock(
        return_value=OrderBookFetchResult(
            snapshot=_make_snapshot(),
            reason_codes=["cache:bypassed"],
        ),
    )
    mcp = _build_server(service)
    async with Client(mcp) as client:
        await client.call_tool(
            "get_order_book",
            {
                "venue": "kucoin",
                "symbol": "BTC-USDT",
                "depth": 20,
                "force_refresh": True,
            },
        )
    call_kwargs = service.fetch_order_book.call_args.kwargs
    assert call_kwargs["depth"] == 20
    assert call_kwargs["force_refresh"] is True


@pytest.mark.asyncio
async def test_get_order_book_symbol_not_found_surfaces_tool_error() -> None:
    service = MagicMock(spec=OrderBookService)
    service.fetch_order_book = AsyncMock(
        side_effect=SymbolNotFoundError(
            user_input="DOGE-USDT",
            venue="kucoin",
        ),
    )
    mcp = _build_server(service)
    async with Client(mcp) as client:
        with pytest.raises(ToolError) as exc_info:
            await client.call_tool(
                "get_order_book",
                {"venue": "kucoin", "symbol": "DOGE-USDT", "depth": 50},
            )
    assert "DOGE-USDT" in str(exc_info.value)
