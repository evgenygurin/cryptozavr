"""In-memory Client(mcp) tests for the analytics single-strategy tools."""

from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from cryptozavr.application.services.analytics_service import AnalyticsService
from cryptozavr.application.services.market_analyzer import AnalysisReport
from cryptozavr.application.strategies.base import AnalysisResult
from cryptozavr.domain.exceptions import SymbolNotFoundError
from cryptozavr.domain.quality import Confidence
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.mcp.lifespan_state import LIFESPAN_KEYS
from cryptozavr.mcp.tools.analytics import (
    register_compute_vwap_tool,
    register_support_resistance_tool,
    register_volatility_regime_tool,
)


def _symbol():
    return SymbolRegistry().get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )


def _result_vwap() -> AnalysisResult:
    return AnalysisResult(
        strategy="vwap",
        findings={
            "vwap": Decimal("100.5"),
            "total_volume": Decimal("123"),
            "bars_used": 50,
        },
        confidence=Confidence.HIGH,
    )


def _result_sr() -> AnalysisResult:
    return AnalysisResult(
        strategy="support_resistance",
        findings={
            "supports": (Decimal("95"), Decimal("92")),
            "resistances": (Decimal("105"), Decimal("108")),
            "pivots_found": 8,
        },
        confidence=Confidence.MEDIUM,
    )


def _result_vol() -> AnalysisResult:
    return AnalysisResult(
        strategy="volatility_regime",
        findings={
            "atr": Decimal("2.4"),
            "atr_pct": Decimal("2.38"),
            "regime": "normal",
            "bars_used": 50,
        },
        confidence=Confidence.HIGH,
    )


def _report(result: AnalysisResult) -> AnalysisReport:
    return AnalysisReport(
        symbol=_symbol(),
        timeframe=Timeframe.M15,
        results=(result,),
    )


def _build_server(
    service: MagicMock,
    registrar,
) -> FastMCP:
    @asynccontextmanager
    async def lifespan(server):
        yield {LIFESPAN_KEYS.analytics_service: service}

    mcp = FastMCP(name="test", version="0.0.0", lifespan=lifespan)
    registrar(mcp)
    return mcp


class TestComputeVwapTool:
    @pytest.mark.asyncio
    async def test_returns_dto_with_reason_codes(self) -> None:
        service = MagicMock(spec=AnalyticsService)
        service.analyze = AsyncMock(
            return_value=(_report(_result_vwap()), ["cache:miss", "staleness:fresh"]),
        )
        mcp = _build_server(service, register_compute_vwap_tool)
        async with Client(mcp) as client:
            result = await client.call_tool(
                "compute_vwap",
                {
                    "venue": "kucoin",
                    "symbol": "BTC-USDT",
                    "timeframe": "15m",
                },
            )
        payload = result.structured_content
        assert payload["strategy"] == "vwap"
        assert payload["confidence"] == "high"
        assert payload["findings"]["vwap"] == "100.5"
        assert payload["findings"]["bars_used"] == 50
        assert payload["reason_codes"] == ["cache:miss", "staleness:fresh"]

    @pytest.mark.asyncio
    async def test_forwards_params_to_service(self) -> None:
        service = MagicMock(spec=AnalyticsService)
        service.analyze = AsyncMock(
            return_value=(_report(_result_vwap()), ["cache:miss"]),
        )
        mcp = _build_server(service, register_compute_vwap_tool)
        async with Client(mcp) as client:
            await client.call_tool(
                "compute_vwap",
                {
                    "venue": "kucoin",
                    "symbol": "BTC-USDT",
                    "timeframe": "1h",
                    "limit": 300,
                    "force_refresh": True,
                },
            )
        service.analyze.assert_awaited_once_with(
            venue="kucoin",
            symbol="BTC-USDT",
            timeframe=Timeframe.H1,
            limit=300,
            force_refresh=True,
            strategy_names=("vwap",),
        )

    @pytest.mark.asyncio
    async def test_unknown_timeframe_raises_tool_error(self) -> None:
        service = MagicMock(spec=AnalyticsService)
        service.analyze = AsyncMock()
        mcp = _build_server(service, register_compute_vwap_tool)
        async with Client(mcp) as client:
            with pytest.raises(ToolError) as exc:
                await client.call_tool(
                    "compute_vwap",
                    {
                        "venue": "kucoin",
                        "symbol": "BTC-USDT",
                        "timeframe": "7m",
                    },
                )
        assert "unknown timeframe" in str(exc.value).lower()
        service.analyze.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_propagates_domain_error_as_tool_error(self) -> None:
        service = MagicMock(spec=AnalyticsService)
        service.analyze = AsyncMock(
            side_effect=SymbolNotFoundError(user_input="DOGE-USDT", venue="kucoin"),
        )
        mcp = _build_server(service, register_compute_vwap_tool)
        async with Client(mcp) as client:
            with pytest.raises(ToolError) as exc:
                await client.call_tool(
                    "compute_vwap",
                    {
                        "venue": "kucoin",
                        "symbol": "DOGE-USDT",
                        "timeframe": "15m",
                    },
                )
        assert "DOGE-USDT" in str(exc.value)


class TestSupportResistanceTool:
    @pytest.mark.asyncio
    async def test_returns_clustered_levels(self) -> None:
        service = MagicMock(spec=AnalyticsService)
        service.analyze = AsyncMock(
            return_value=(_report(_result_sr()), ["cache:hit", "staleness:fresh"]),
        )
        mcp = _build_server(service, register_support_resistance_tool)
        async with Client(mcp) as client:
            result = await client.call_tool(
                "identify_support_resistance",
                {
                    "venue": "kucoin",
                    "symbol": "BTC-USDT",
                    "timeframe": "15m",
                },
            )
        payload = result.structured_content
        assert payload["strategy"] == "support_resistance"
        assert payload["confidence"] == "medium"
        assert payload["findings"]["supports"] == ["95", "92"]
        assert payload["findings"]["resistances"] == ["105", "108"]
        assert payload["findings"]["pivots_found"] == 8


class TestVolatilityRegimeTool:
    @pytest.mark.asyncio
    async def test_returns_regime(self) -> None:
        service = MagicMock(spec=AnalyticsService)
        service.analyze = AsyncMock(
            return_value=(_report(_result_vol()), ["cache:miss", "staleness:fresh"]),
        )
        mcp = _build_server(service, register_volatility_regime_tool)
        async with Client(mcp) as client:
            result = await client.call_tool(
                "volatility_regime",
                {
                    "venue": "kucoin",
                    "symbol": "BTC-USDT",
                    "timeframe": "1h",
                },
            )
        payload = result.structured_content
        assert payload["strategy"] == "volatility_regime"
        assert payload["findings"]["regime"] == "normal"
        assert payload["findings"]["atr_pct"] == "2.38"
