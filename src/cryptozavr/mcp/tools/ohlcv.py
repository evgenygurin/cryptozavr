"""get_ohlcv MCP tool registration."""

from __future__ import annotations

from typing import Annotated, Any, cast

from fastmcp import Context, FastMCP
from pydantic import Field

from cryptozavr.application.services.ohlcv_service import OhlcvService
from cryptozavr.domain.exceptions import DomainError, ValidationError
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.mcp.dtos import OHLCVSeriesDTO
from cryptozavr.mcp.errors import domain_to_tool_error


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
    ) -> OHLCVSeriesDTO:
        try:
            tf = Timeframe(timeframe)
        except ValueError as exc:
            raise domain_to_tool_error(
                ValidationError(f"unknown timeframe: {timeframe!r}"),
            ) from exc
        service = cast(
            OhlcvService,
            cast(Any, ctx.lifespan_context).ohlcv_service,
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
        return OHLCVSeriesDTO.from_domain(result.series, result.reason_codes)
