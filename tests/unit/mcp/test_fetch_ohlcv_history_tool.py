"""In-memory Client(mcp) tests for the fetch_ohlcv_history tool."""

from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from cryptozavr.application.services.ohlcv_service import (
    OhlcvFetchResult,
    OhlcvService,
)
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
from cryptozavr.mcp.lifespan_state import LIFESPAN_KEYS
from cryptozavr.mcp.tools.history import register_fetch_ohlcv_history_tool

_TF_MS = Timeframe.H1.to_milliseconds()
_START = 1_700_000_000_000


def _symbol():
    return SymbolRegistry().get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )


def _candle(ms: int) -> OHLCVCandle:
    return OHLCVCandle(
        opened_at=Instant.from_ms(ms),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        volume=Decimal("5"),
    )


def _quality() -> DataQuality:
    return DataQuality(
        source=Provenance(venue_id="kucoin", endpoint="fetch_ohlcv"),
        fetched_at=Instant.from_ms(_START),
        staleness=Staleness.FRESH,
        confidence=Confidence.HIGH,
        cache_hit=False,
    )


def _series(candles: tuple[OHLCVCandle, ...]) -> OHLCVSeries:
    first = candles[0].opened_at.to_ms() if candles else _START
    last = candles[-1].opened_at.to_ms() + _TF_MS if candles else _START + 1
    return OHLCVSeries(
        symbol=_symbol(),
        timeframe=Timeframe.H1,
        candles=candles,
        range=TimeRange(
            start=Instant.from_ms(first),
            end=Instant.from_ms(last),
        ),
        quality=_quality(),
    )


def _result(candles: tuple[OHLCVCandle, ...], codes: list[str]) -> OhlcvFetchResult:
    return OhlcvFetchResult(series=_series(candles), reason_codes=codes)


def _build_server(service: MagicMock) -> FastMCP:
    @asynccontextmanager
    async def lifespan(server):
        yield {LIFESPAN_KEYS.ohlcv_service: service}

    mcp = FastMCP(name="test", version="0.0.0", lifespan=lifespan)
    register_fetch_ohlcv_history_tool(mcp)
    return mcp


class TestFetchOhlcvHistoryTool:
    @pytest.mark.asyncio
    async def test_returns_envelope_with_history_dto(self) -> None:
        candles = tuple(_candle(_START + i * _TF_MS) for i in range(5))
        service = MagicMock(spec=OhlcvService)
        service.fetch_ohlcv = AsyncMock(
            return_value=_result(candles, ["cache:miss", "provider:kucoin"]),
        )
        mcp = _build_server(service)
        async with Client(mcp) as client:
            result = await client.call_tool(
                "fetch_ohlcv_history",
                {
                    "venue": "kucoin",
                    "symbol": "BTC-USDT",
                    "timeframe": "1h",
                    "since_ms": _START,
                    "until_ms": _START + _TF_MS * 5,
                    "chunk_size": 500,
                },
            )
        payload = result.structured_content
        assert "data" in payload
        assert "reasoning" in payload
        assert "quality" in payload
        assert payload["data"]["venue"] == "kucoin"
        assert payload["data"]["timeframe"] == "1h"
        assert payload["data"]["chunks_fetched"] == 1
        assert len(payload["data"]["candles"]) == 5
        assert payload["reasoning"]["chain_decisions"] == [
            "cache:miss",
            "provider:kucoin",
        ]
        assert len(payload["reasoning"]["query_id"]) == 12
        assert payload["quality"]["staleness"] == "fresh"

    @pytest.mark.asyncio
    async def test_walks_multiple_chunks_and_merges_codes(self) -> None:
        first = tuple(_candle(_START + i * _TF_MS) for i in range(3))
        second = tuple(_candle(_START + (3 + i) * _TF_MS) for i in range(2))
        service = MagicMock(spec=OhlcvService)
        service.fetch_ohlcv = AsyncMock(
            side_effect=[
                _result(first, ["chunk:0", "cache:miss"]),
                _result(second, ["chunk:1", "cache:hit"]),
            ],
        )
        mcp = _build_server(service)
        async with Client(mcp) as client:
            result = await client.call_tool(
                "fetch_ohlcv_history",
                {
                    "venue": "kucoin",
                    "symbol": "BTC-USDT",
                    "timeframe": "1h",
                    "since_ms": _START,
                    "until_ms": _START + _TF_MS * 5,
                    "chunk_size": 3,
                },
            )
        payload = result.structured_content
        assert payload["data"]["chunks_fetched"] == 2
        assert len(payload["data"]["candles"]) == 5
        assert payload["reasoning"]["chain_decisions"] == [
            "chunk:0",
            "cache:miss",
            "chunk:1",
            "cache:hit",
        ]

    @pytest.mark.asyncio
    async def test_inverted_range_surfaces_as_tool_error(self) -> None:
        service = MagicMock(spec=OhlcvService)
        service.fetch_ohlcv = AsyncMock()
        mcp = _build_server(service)
        async with Client(mcp) as client:
            with pytest.raises(ToolError) as exc:
                await client.call_tool(
                    "fetch_ohlcv_history",
                    {
                        "venue": "kucoin",
                        "symbol": "BTC-USDT",
                        "timeframe": "1h",
                        "since_ms": _START + _TF_MS,
                        "until_ms": _START,
                    },
                )
        assert "strictly greater" in str(exc.value).lower()
        service.fetch_ohlcv.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unknown_timeframe_raises(self) -> None:
        service = MagicMock(spec=OhlcvService)
        service.fetch_ohlcv = AsyncMock()
        mcp = _build_server(service)
        async with Client(mcp) as client:
            with pytest.raises(ToolError) as exc:
                await client.call_tool(
                    "fetch_ohlcv_history",
                    {
                        "venue": "kucoin",
                        "symbol": "BTC-USDT",
                        "timeframe": "7m",
                        "since_ms": _START,
                        "until_ms": _START + _TF_MS * 5,
                    },
                )
        assert "unknown timeframe" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_domain_error_propagates_as_tool_error(self) -> None:
        service = MagicMock(spec=OhlcvService)
        service.fetch_ohlcv = AsyncMock(
            side_effect=SymbolNotFoundError(user_input="XRP-USDT", venue="kucoin"),
        )
        mcp = _build_server(service)
        async with Client(mcp) as client:
            with pytest.raises(ToolError) as exc:
                await client.call_tool(
                    "fetch_ohlcv_history",
                    {
                        "venue": "kucoin",
                        "symbol": "XRP-USDT",
                        "timeframe": "1h",
                        "since_ms": _START,
                        "until_ms": _START + _TF_MS * 5,
                    },
                )
        assert "XRP-USDT" in str(exc.value)

    @pytest.mark.asyncio
    async def test_progress_events_between_chunks(self) -> None:
        first = tuple(_candle(_START + i * _TF_MS) for i in range(3))
        second = tuple(_candle(_START + (3 + i) * _TF_MS) for i in range(2))
        service = MagicMock(spec=OhlcvService)
        service.fetch_ohlcv = AsyncMock(
            side_effect=[
                _result(first, ["c0"]),
                _result(second, ["c1"]),
            ],
        )
        events: list[tuple[float, float | None, str | None]] = []

        async def handler(progress, total, message):
            events.append((progress, total, message))

        mcp = _build_server(service)
        async with Client(mcp, progress_handler=handler) as client:
            await client.call_tool(
                "fetch_ohlcv_history",
                {
                    "venue": "kucoin",
                    "symbol": "BTC-USDT",
                    "timeframe": "1h",
                    "since_ms": _START,
                    "until_ms": _START + _TF_MS * 5,
                    "chunk_size": 3,
                },
            )
        assert len(events) >= 3
        assert events[0][0] == 0
        assert events[-1][0] == events[-1][1]
        assert any("done" in (m or "").lower() for _, _, m in events)
