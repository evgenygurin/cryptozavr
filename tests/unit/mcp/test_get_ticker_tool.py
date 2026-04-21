"""In-memory Client(mcp) tests for the get_ticker tool."""

from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from cryptozavr.application.services.ticker_service import (
    TickerFetchResult,
    TickerService,
)
from cryptozavr.domain.exceptions import SymbolNotFoundError
from cryptozavr.domain.market_data import Ticker
from cryptozavr.domain.quality import (
    Confidence,
    DataQuality,
    Provenance,
    Staleness,
)
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.mcp.lifespan_state import LIFESPAN_KEYS
from cryptozavr.mcp.tools.ticker import register_ticker_tool


def _make_ticker() -> Ticker:
    symbol = SymbolRegistry().get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )
    return Ticker(
        symbol=symbol,
        last=Decimal("100"),
        observed_at=Instant.from_ms(1_700_000_000_000),
        quality=DataQuality(
            source=Provenance(venue_id="kucoin", endpoint="fetch_ticker"),
            fetched_at=Instant.from_ms(1_700_000_000_000),
            staleness=Staleness.FRESH,
            confidence=Confidence.HIGH,
            cache_hit=False,
        ),
    )


def _build_server(mock_service) -> FastMCP:
    @asynccontextmanager
    async def lifespan(server):
        yield {LIFESPAN_KEYS.ticker_service: mock_service}

    mcp = FastMCP(name="test", version="0.0.0", lifespan=lifespan)
    register_ticker_tool(mcp)
    return mcp


@pytest.mark.asyncio
async def test_get_ticker_returns_dto_fields() -> None:
    # Use spec= so MagicMock is not treated as AbstractAsyncContextManager
    # by FastMCP's Depends() resolution engine.
    service = MagicMock(spec=TickerService)
    service.fetch_ticker = AsyncMock(
        return_value=TickerFetchResult(
            ticker=_make_ticker(),
            reason_codes=["venue:healthy", "cache:miss", "provider:called"],
        ),
    )
    mcp = _build_server(service)
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_ticker",
            {"venue": "kucoin", "symbol": "BTC-USDT"},
        )
    # result.data is None when FastMCP can't parse structured_content schema
    # (regex in Decimal validator unsupported by pydantic-core). Fall back to
    # structured_content which is always populated from the raw JSON payload.
    payload = result.structured_content
    assert payload["venue"] == "kucoin"
    assert payload["symbol"] == "BTC-USDT"
    assert payload["last"] == "100"
    assert payload["reason_codes"] == [
        "venue:healthy",
        "cache:miss",
        "provider:called",
    ]
    service.fetch_ticker.assert_awaited_once_with(
        venue="kucoin",
        symbol="BTC-USDT",
        force_refresh=False,
    )


@pytest.mark.asyncio
async def test_get_ticker_forwards_force_refresh() -> None:
    service = MagicMock(spec=TickerService)
    service.fetch_ticker = AsyncMock(
        return_value=TickerFetchResult(
            ticker=_make_ticker(),
            reason_codes=["cache:bypassed"],
        ),
    )
    mcp = _build_server(service)
    async with Client(mcp) as client:
        await client.call_tool(
            "get_ticker",
            {"venue": "kucoin", "symbol": "BTC-USDT", "force_refresh": True},
        )
    service.fetch_ticker.assert_awaited_once_with(
        venue="kucoin",
        symbol="BTC-USDT",
        force_refresh=True,
    )


@pytest.mark.asyncio
async def test_symbol_not_found_surfaces_as_tool_error() -> None:
    service = MagicMock(spec=TickerService)
    service.fetch_ticker = AsyncMock(
        side_effect=SymbolNotFoundError(user_input="DOGE-USDT", venue="kucoin"),
    )
    mcp = _build_server(service)
    async with Client(mcp) as client:
        with pytest.raises(ToolError) as exc_info:
            await client.call_tool(
                "get_ticker",
                {"venue": "kucoin", "symbol": "DOGE-USDT"},
            )
    assert "DOGE-USDT" in str(exc_info.value)
