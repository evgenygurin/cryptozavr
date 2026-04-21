"""get_trades MCP tool registration."""

from __future__ import annotations

from typing import Annotated, Any, cast

from fastmcp import Context, FastMCP
from pydantic import Field

from cryptozavr.application.services.trades_service import TradesService
from cryptozavr.domain.exceptions import DomainError
from cryptozavr.mcp.dtos import TradesDTO
from cryptozavr.mcp.errors import domain_to_tool_error


def register_trades_tool(mcp: FastMCP) -> None:
    """Attach get_trades tool to the given FastMCP instance."""

    @mcp.tool(
        name="get_trades",
        description=(
            "Fetch recent trades for a symbol on a venue. Non-cached in "
            "M2 — each call reaches the provider. Returns up to `limit` "
            "most recent trades; passes `since` through unchanged."
        ),
        tags={"market", "public", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def get_trades(
        venue: Annotated[
            str,
            Field(description="Venue id. Supported: kucoin, coingecko."),
        ],
        symbol: Annotated[
            str,
            Field(description="Native symbol, e.g. BTC-USDT (kucoin)."),
        ],
        ctx: Context,
        limit: Annotated[
            int,
            Field(ge=1, le=1000, description="Max trades to return (1..1000)."),
        ] = 100,
        force_refresh: Annotated[
            bool,
            Field(description="Passes through to the chain; non-cached path."),
        ] = False,
    ) -> TradesDTO:
        service = cast(
            TradesService,
            cast(Any, ctx.lifespan_context).trades_service,
        )
        try:
            result = await service.fetch_trades(
                venue=venue,
                symbol=symbol,
                limit=limit,
                force_refresh=force_refresh,
            )
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc
        return TradesDTO.from_domain(
            venue=result.venue,
            symbol=result.symbol,
            trades=result.trades,
            reason_codes=result.reason_codes,
        )
