"""get_trades MCP tool registration (v3 idiomatic: Depends + ctx.info)."""

from __future__ import annotations

from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.dependencies import Depends
from pydantic import Field

from cryptozavr.application.services.trades_service import TradesService
from cryptozavr.domain.exceptions import DomainError
from cryptozavr.mcp.dtos import TradesDTO
from cryptozavr.mcp.errors import domain_to_tool_error
from cryptozavr.mcp.lifespan_state import get_trades_service

# Module-level singleton — avoids B008 (function call in default argument).
_TRADES_SVC: TradesService = Depends(get_trades_service)


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
        service: TradesService = _TRADES_SVC,
    ) -> TradesDTO:
        await ctx.info(
            f"get_trades venue={venue} symbol={symbol} limit={limit} force_refresh={force_refresh}",
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

        await ctx.info(f"reason_codes: {','.join(result.reason_codes)}")
        if "cache:write_failed" in result.reason_codes:
            await ctx.warning(
                "Supabase write-through failed; data valid but not persisted.",
            )
        # Trades have no series-level quality envelope — staleness check skipped.
        return TradesDTO.from_domain(
            venue=result.venue,
            symbol=result.symbol,
            trades=result.trades,
            reason_codes=result.reason_codes,
        )
