"""Analytics MCP tools — single-strategy wrappers + composite snapshot.

v3 idiomatic: Depends + ctx logging + direct DTO return. Single-strategy
tools wrap one AnalysisStrategy; analyze_snapshot runs all three at once
over the same OHLCV fetch and emits progress updates between steps.
"""

from __future__ import annotations

from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.dependencies import Depends
from pydantic import Field

from cryptozavr import __version__
from cryptozavr.application.services.analytics_service import AnalyticsService
from cryptozavr.domain.exceptions import DomainError, ValidationError
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.mcp.dtos import AnalysisReportDTO, AnalysisResultDTO
from cryptozavr.mcp.errors import domain_to_tool_error
from cryptozavr.mcp.lifespan_state import get_analytics_service

_SNAPSHOT_STRATEGIES: tuple[str, ...] = (
    "vwap",
    "support_resistance",
    "volatility_regime",
)

# Module-level singleton — avoids B008 (function call in default argument).
_ANALYTICS_SVC: AnalyticsService = Depends(get_analytics_service)


def _parse_timeframe(raw: str) -> Timeframe:
    try:
        return Timeframe(raw)
    except ValueError as exc:
        raise domain_to_tool_error(
            ValidationError(f"unknown timeframe: {raw!r}"),
        ) from exc


async def _warn_on_quality(ctx: Context, reason_codes: list[str]) -> None:
    await ctx.info(f"reason_codes: {','.join(reason_codes)}")
    if "cache:write_failed" in reason_codes:
        await ctx.warning(
            "Supabase write-through failed; data valid but not persisted.",
        )
    stale = [c for c in reason_codes if c.startswith("staleness:") and c != "staleness:fresh"]
    if stale:
        await ctx.warning(f"{stale[0]} — consider force_refresh=True.")


async def _run_single(
    *,
    service: AnalyticsService,
    strategy: str,
    venue: str,
    symbol: str,
    timeframe: str,
    limit: int,
    force_refresh: bool,
    ctx: Context,
) -> AnalysisResultDTO:
    tf = _parse_timeframe(timeframe)
    await ctx.info(
        f"{strategy} venue={venue} symbol={symbol} timeframe={timeframe} "
        f"limit={limit} force_refresh={force_refresh}",
    )
    try:
        report, reason_codes = await service.analyze(
            venue=venue,
            symbol=symbol,
            timeframe=tf,
            limit=limit,
            force_refresh=force_refresh,
            strategy_names=(strategy,),
        )
    except DomainError as exc:
        raise domain_to_tool_error(exc) from exc

    await _warn_on_quality(ctx, reason_codes)
    return AnalysisResultDTO.from_domain(report.results[0], reason_codes)


def _venue_field() -> object:
    return Field(description="Venue id. Supported: kucoin, coingecko.")


def _symbol_field() -> object:
    return Field(description="Native symbol, e.g. BTC-USDT (kucoin).")


def _timeframe_field() -> object:
    return Field(
        description=("Timeframe code: 1m, 5m, 15m, 1h, 4h, 1d. Validated against Timeframe enum."),
    )


def _limit_field(default: int) -> object:
    return Field(ge=10, le=1000, description=f"Max OHLCV bars to analyse (default {default}).")


def _force_refresh_field() -> object:
    return Field(description="Bypass the Supabase cache.")


def register_compute_vwap_tool(mcp: FastMCP) -> None:
    """Attach compute_vwap tool."""

    @mcp.tool(
        name="compute_vwap",
        description=(
            "Compute Volume-Weighted Average Price (VWAP) over recent OHLCV "
            "candles. Returns vwap (Decimal), total_volume, bars_used, "
            "plus confidence (HIGH if >=10 bars). Pulls OHLCV through the "
            "cached chain; set force_refresh=True to bypass the cache."
        ),
        tags={"analytics", "public", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
        timeout=30.0,
        meta={"strategy": "vwap", "version": __version__},
    )
    async def compute_vwap(
        venue: Annotated[str, _venue_field()],
        symbol: Annotated[str, _symbol_field()],
        timeframe: Annotated[str, _timeframe_field()],
        ctx: Context,
        limit: Annotated[int, _limit_field(200)] = 200,
        force_refresh: Annotated[bool, _force_refresh_field()] = False,
        service: AnalyticsService = _ANALYTICS_SVC,
    ) -> AnalysisResultDTO:
        return await _run_single(
            service=service,
            strategy="vwap",
            venue=venue,
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            force_refresh=force_refresh,
            ctx=ctx,
        )


def register_support_resistance_tool(mcp: FastMCP) -> None:
    """Attach identify_support_resistance tool."""

    @mcp.tool(
        name="identify_support_resistance",
        description=(
            "Detect swing-based support / resistance levels on recent OHLCV. "
            "Returns supports (list of Decimals), resistances (list of "
            "Decimals), pivots_found count, plus HIGH confidence when "
            ">=20 bars analysed."
        ),
        tags={"analytics", "public", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
        timeout=30.0,
        meta={"strategy": "support_resistance", "version": __version__},
    )
    async def identify_support_resistance(
        venue: Annotated[str, _venue_field()],
        symbol: Annotated[str, _symbol_field()],
        timeframe: Annotated[str, _timeframe_field()],
        ctx: Context,
        limit: Annotated[int, _limit_field(200)] = 200,
        force_refresh: Annotated[bool, _force_refresh_field()] = False,
        service: AnalyticsService = _ANALYTICS_SVC,
    ) -> AnalysisResultDTO:
        return await _run_single(
            service=service,
            strategy="support_resistance",
            venue=venue,
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            force_refresh=force_refresh,
            ctx=ctx,
        )


def register_volatility_regime_tool(mcp: FastMCP) -> None:
    """Attach volatility_regime tool."""

    @mcp.tool(
        name="volatility_regime",
        description=(
            "Classify volatility regime via ATR as % of last close: calm "
            "(<1%), normal (<3%), high (<6%), extreme (>=6%). Returns "
            "atr (Decimal), atr_pct (Decimal), regime (str), bars_used."
        ),
        tags={"analytics", "public", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
        timeout=30.0,
        meta={"strategy": "volatility_regime", "version": __version__},
    )
    async def volatility_regime(
        venue: Annotated[str, _venue_field()],
        symbol: Annotated[str, _symbol_field()],
        timeframe: Annotated[str, _timeframe_field()],
        ctx: Context,
        limit: Annotated[int, _limit_field(200)] = 200,
        force_refresh: Annotated[bool, _force_refresh_field()] = False,
        service: AnalyticsService = _ANALYTICS_SVC,
    ) -> AnalysisResultDTO:
        return await _run_single(
            service=service,
            strategy="volatility_regime",
            venue=venue,
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            force_refresh=force_refresh,
            ctx=ctx,
        )


def register_analyze_snapshot_tool(mcp: FastMCP) -> None:
    """Attach analyze_snapshot composite tool (all 3 strategies)."""

    @mcp.tool(
        name="analyze_snapshot",
        description=(
            "Composite analysis: runs VWAP, support/resistance, and "
            "volatility-regime strategies over the same OHLCV fetch and "
            "returns a single AnalysisReport. Cheaper than 3 separate "
            "tool calls (one OHLCV fetch shared across strategies). "
            "Emits progress updates between strategies."
        ),
        tags={"analytics", "public", "read-only", "composite"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
        timeout=60.0,
        meta={
            "strategies": list(_SNAPSHOT_STRATEGIES),
            "version": __version__,
        },
    )
    async def analyze_snapshot(
        venue: Annotated[str, _venue_field()],
        symbol: Annotated[str, _symbol_field()],
        timeframe: Annotated[str, _timeframe_field()],
        ctx: Context,
        limit: Annotated[int, _limit_field(200)] = 200,
        force_refresh: Annotated[bool, _force_refresh_field()] = False,
        service: AnalyticsService = _ANALYTICS_SVC,
    ) -> AnalysisReportDTO:
        tf = _parse_timeframe(timeframe)
        total_steps = len(_SNAPSHOT_STRATEGIES) + 1  # +1 for OHLCV fetch
        await ctx.info(
            f"analyze_snapshot venue={venue} symbol={symbol} "
            f"timeframe={timeframe} limit={limit} force_refresh={force_refresh}",
        )
        await ctx.report_progress(
            progress=0,
            total=total_steps,
            message="fetching OHLCV",
        )
        try:
            report, reason_codes = await service.analyze(
                venue=venue,
                symbol=symbol,
                timeframe=tf,
                limit=limit,
                force_refresh=force_refresh,
                strategy_names=_SNAPSHOT_STRATEGIES,
            )
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc

        for idx, strategy in enumerate(_SNAPSHOT_STRATEGIES, start=1):
            await ctx.report_progress(
                progress=idx,
                total=total_steps,
                message=f"{strategy} done",
            )

        await ctx.report_progress(
            progress=total_steps,
            total=total_steps,
            message="complete",
        )
        await _warn_on_quality(ctx, reason_codes)
        return AnalysisReportDTO.from_domain(report, reason_codes)


def register_analytics_tools(mcp: FastMCP) -> None:
    """Register all analytics tools (3 single-strategy + snapshot)."""
    register_compute_vwap_tool(mcp)
    register_support_resistance_tool(mcp)
    register_volatility_regime_tool(mcp)
    register_analyze_snapshot_tool(mcp)
