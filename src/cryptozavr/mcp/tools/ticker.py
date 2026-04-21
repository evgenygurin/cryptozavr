"""get_ticker MCP tool registration (v3 idiomatic: Depends + ctx.info)."""

from __future__ import annotations

from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.dependencies import Depends
from pydantic import Field

from cryptozavr.application.services.ticker_service import TickerService
from cryptozavr.domain.exceptions import DomainError
from cryptozavr.mcp.dtos import TickerDTO
from cryptozavr.mcp.errors import domain_to_tool_error
from cryptozavr.mcp.lifespan_state import get_ticker_service

# Module-level singleton — avoids B008 (function call in default argument).
_TICKER_SVC: TickerService = Depends(get_ticker_service)


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
        service: TickerService = _TICKER_SVC,
    ) -> TickerDTO:
        await ctx.info(
            f"get_ticker venue={venue} symbol={symbol} force_refresh={force_refresh}",
        )
        try:
            result = await service.fetch_ticker(
                venue=venue,
                symbol=symbol,
                force_refresh=force_refresh,
            )
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc

        await ctx.info(f"reason_codes: {','.join(result.reason_codes)}")
        if "cache:write_failed" in result.reason_codes:
            await ctx.warning(
                "Supabase write-through failed; data valid but not persisted.",
            )
        staleness = result.ticker.quality.staleness.name.lower()
        if staleness != "fresh":
            await ctx.warning(
                f"staleness={staleness} — consider force_refresh=True.",
            )
        return TickerDTO.from_domain(result.ticker, result.reason_codes)
