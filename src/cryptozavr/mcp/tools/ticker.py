"""get_ticker MCP tool registration."""

from __future__ import annotations

from typing import Annotated, Any, cast

from fastmcp import Context, FastMCP
from pydantic import Field

from cryptozavr.application.services.ticker_service import TickerService
from cryptozavr.domain.exceptions import DomainError
from cryptozavr.mcp.dtos import TickerDTO
from cryptozavr.mcp.errors import domain_to_tool_error


def register_ticker_tool(mcp: FastMCP) -> None:
    """Attach get_ticker tool to the given FastMCP instance."""

    @mcp.tool(
        name="get_ticker",
        description=(
            "Fetch the latest ticker (last, bid, ask, 24h volume) for a "
            "symbol on a venue. Goes through venue-health → symbol-exists "
            "→ staleness-bypass → supabase-cache → provider-fetch chain. "
            "Set force_refresh=True to skip the cache."
        ),
        tags={"market", "public", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def get_ticker(
        venue: Annotated[
            str,
            Field(description="Venue id. Supported: kucoin, coingecko."),
        ],
        symbol: Annotated[
            str,
            Field(description="Native symbol, e.g. BTC-USDT (kucoin)."),
        ],
        ctx: Context,
        force_refresh: Annotated[
            bool,
            Field(description="Bypass the Supabase cache."),
        ] = False,
    ) -> TickerDTO:
        # ctx.lifespan_context is typed as dict[str, Any] in FastMCP stubs,
        # but at runtime it holds whatever the lifespan yielded (here: AppState).
        service = cast(TickerService, cast(Any, ctx.lifespan_context).ticker_service)
        try:
            result = await service.fetch_ticker(
                venue=venue,
                symbol=symbol,
                force_refresh=force_refresh,
            )
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc
        return TickerDTO.from_domain(result.ticker, result.reason_codes)
