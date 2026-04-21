"""get_ohlcv MCP tool registration (v3 idiomatic: Depends + ctx.info)."""

from __future__ import annotations

from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.dependencies import Depends
from pydantic import Field

from cryptozavr.application.services.ohlcv_service import OhlcvService
from cryptozavr.domain.exceptions import DomainError, ValidationError
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.mcp.dtos import OHLCVSeriesDTO
from cryptozavr.mcp.errors import domain_to_tool_error
from cryptozavr.mcp.lifespan_state import get_ohlcv_service

# Module-level singleton — avoids B008 (function call in default argument).
_OHLCV_SVC: OhlcvService = Depends(get_ohlcv_service)


def register_ohlcv_tool(mcp: FastMCP) -> None:
    """Attach get_ohlcv tool to the given FastMCP instance."""

    @mcp.tool(
        name="get_ohlcv",
        description=(
            "Fetch OHLCV candles for a symbol on a venue at a given "
            "timeframe. Goes through the same 5-handler chain as "
            "get_ticker (venue-health → symbol-exists → staleness-bypass "
            "→ supabase-cache → provider-fetch). Set force_refresh=True "
            "to skip the cache."
        ),
        tags={"market", "public", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_ohlcv(
        venue: Annotated[
            str,
            Field(description="Venue id. Supported: kucoin, coingecko."),
        ],
        symbol: Annotated[
            str,
            Field(description="Native symbol, e.g. BTC-USDT (kucoin)."),
        ],
        timeframe: Annotated[
            str,
            Field(
                description=(
                    "Timeframe code: 1m, 5m, 15m, 1h, 4h, 1d. Validated against Timeframe enum."
                ),
            ),
        ],
        ctx: Context,
        limit: Annotated[
            int,
            Field(ge=1, le=1000, description="Max candles to return (1..1000)."),
        ] = 500,
        force_refresh: Annotated[
            bool,
            Field(description="Bypass the Supabase cache."),
        ] = False,
        service: OhlcvService = _OHLCV_SVC,
    ) -> OHLCVSeriesDTO:
        try:
            tf = Timeframe(timeframe)
        except ValueError as exc:
            raise domain_to_tool_error(
                ValidationError(f"unknown timeframe: {timeframe!r}"),
            ) from exc

        await ctx.info(
            f"get_ohlcv venue={venue} symbol={symbol} timeframe={timeframe} "
            f"limit={limit} force_refresh={force_refresh}",
        )
        try:
            result = await service.fetch_ohlcv(
                venue=venue,
                symbol=symbol,
                timeframe=tf,
                limit=limit,
                force_refresh=force_refresh,
            )
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc

        await ctx.info(f"reason_codes: {','.join(result.reason_codes)}")
        if "cache:write_failed" in result.reason_codes:
            await ctx.warning(
                "Supabase write-through failed; data valid but not persisted.",
            )
        staleness = result.series.quality.staleness.name.lower()
        if staleness != "fresh":
            await ctx.warning(
                f"staleness={staleness} — consider force_refresh=True.",
            )
        return OHLCVSeriesDTO.from_domain(result.series, result.reason_codes)
