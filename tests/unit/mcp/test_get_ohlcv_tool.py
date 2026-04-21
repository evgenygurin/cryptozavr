"""In-memory Client(mcp) tests for the get_ohlcv tool."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from cryptozavr.application.services.ohlcv_service import OhlcvFetchResult
from cryptozavr.domain.exceptions import SymbolNotFoundError
from cryptozavr.domain.market_data import OHLCVCandle, OHLCVSeries
from cryptozavr.domain.quality import (
    Confidence,
    DataQuality,
    Provenance,
    Staleness,
)
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Timeframe, TimeRange
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.mcp.tools.ohlcv import register_ohlcv_tool


@dataclass(slots=True)
class _AppState:
    ohlcv_service: object


def _make_series() -> OHLCVSeries:
    symbol = SymbolRegistry().get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )
    candle = OHLCVCandle(
        opened_at=Instant.from_ms(1_700_000_000_000),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("95"),
        close=Decimal("105"),
        volume=Decimal("1000"),
    )
    return OHLCVSeries(
        symbol=symbol,
        timeframe=Timeframe.M1,
        candles=(candle,),
        range=TimeRange(
            start=Instant.from_ms(1_700_000_000_000),
            end=Instant.from_ms(1_700_000_060_000),
        ),
        quality=DataQuality(
            source=Provenance(venue_id="kucoin", endpoint="fetch_ohlcv"),
            fetched_at=Instant.from_ms(1_700_000_060_000),
            staleness=Staleness.FRESH,
            confidence=Confidence.HIGH,
            cache_hit=False,
        ),
    )


def _build_server(mock_service) -> FastMCP:
    @asynccontextmanager
    async def lifespan(server):
        yield _AppState(ohlcv_service=mock_service)

    mcp = FastMCP(name="test", version="0.0.0", lifespan=lifespan)
    register_ohlcv_tool(mcp)
    return mcp


@pytest.mark.asyncio
async def test_get_ohlcv_returns_dto_fields() -> None:
    service = MagicMock()
    service.fetch_ohlcv = AsyncMock(
        return_value=OhlcvFetchResult(
            series=_make_series(),
            reason_codes=["venue:healthy", "cache:miss", "provider:called"],
        ),
    )
    mcp = _build_server(service)
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_ohlcv",
            {
                "venue": "kucoin",
                "symbol": "BTC-USDT",
                "timeframe": "1m",
                "limit": 100,
            },
        )
    payload = result.structured_content
    assert payload["venue"] == "kucoin"
    assert payload["symbol"] == "BTC-USDT"
    assert payload["timeframe"] == "1m"
    assert len(payload["candles"]) == 1
    assert payload["reason_codes"] == [
        "venue:healthy",
        "cache:miss",
        "provider:called",
    ]
    service.fetch_ohlcv.assert_awaited_once()
    call_kwargs = service.fetch_ohlcv.call_args.kwargs
    assert call_kwargs["venue"] == "kucoin"
    assert call_kwargs["symbol"] == "BTC-USDT"
    assert call_kwargs["timeframe"] == Timeframe.M1
    assert call_kwargs["limit"] == 100
    assert call_kwargs["force_refresh"] is False


@pytest.mark.asyncio
async def test_get_ohlcv_forwards_force_refresh() -> None:
    service = MagicMock()
    service.fetch_ohlcv = AsyncMock(
        return_value=OhlcvFetchResult(
            series=_make_series(),
            reason_codes=["cache:bypassed"],
        ),
    )
    mcp = _build_server(service)
    async with Client(mcp) as client:
        await client.call_tool(
            "get_ohlcv",
            {
                "venue": "kucoin",
                "symbol": "BTC-USDT",
                "timeframe": "1m",
                "limit": 50,
                "force_refresh": True,
            },
        )
    call_kwargs = service.fetch_ohlcv.call_args.kwargs
    assert call_kwargs["force_refresh"] is True
    assert call_kwargs["limit"] == 50


@pytest.mark.asyncio
async def test_get_ohlcv_symbol_not_found_surfaces_tool_error() -> None:
    service = MagicMock()
    service.fetch_ohlcv = AsyncMock(
        side_effect=SymbolNotFoundError(user_input="DOGE-USDT", venue="kucoin"),
    )
    mcp = _build_server(service)
    async with Client(mcp) as client:
        with pytest.raises(ToolError) as exc_info:
            await client.call_tool(
                "get_ohlcv",
                {
                    "venue": "kucoin",
                    "symbol": "DOGE-USDT",
                    "timeframe": "1m",
                    "limit": 100,
                },
            )
    assert "DOGE-USDT" in str(exc_info.value)
