"""get_order_book MCP tool registration."""

from __future__ import annotations

from typing import Annotated, Any, cast

from fastmcp import Context, FastMCP
from pydantic import Field

from cryptozavr.application.services.order_book_service import (
    OrderBookService,
)
from cryptozavr.domain.exceptions import DomainError
from cryptozavr.mcp.dtos import OrderBookDTO
from cryptozavr.mcp.errors import domain_to_tool_error


def register_order_book_tool(mcp: FastMCP) -> None:
    """Attach get_order_book tool to the given FastMCP instance."""

    @mcp.tool(
        name="get_order_book",
        description=(
            "Fetch the current order-book snapshot (bids + asks) for a "
            "symbol on a venue. Goes through the full 5-handler chain; "
            "order-book is non-cached in M2, so each call reaches the "
            "provider. Convenience spread/spread_bps included."
        ),
        tags={"market", "public", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def get_order_book(
        venue: Annotated[
            str,
            Field(description="Venue id. Supported: kucoin, coingecko."),
        ],
        symbol: Annotated[
            str,
            Field(description="Native symbol, e.g. BTC-USDT (kucoin)."),
        ],
        ctx: Context,
        depth: Annotated[
            int,
            Field(ge=1, le=200, description="Levels per side (1..200)."),
        ] = 50,
        force_refresh: Annotated[
            bool,
            Field(description="Passes through to the chain; non-cached path."),
        ] = False,
    ) -> OrderBookDTO:
        service = cast(
            OrderBookService,
            cast(Any, ctx.lifespan_context).order_book_service,
        )
        try:
            result = await service.fetch_order_book(
                venue=venue,
                symbol=symbol,
                depth=depth,
                force_refresh=force_refresh,
            )
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc
        return OrderBookDTO.from_domain(result.snapshot, result.reason_codes)
