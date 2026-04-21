"""Discovery MCP tools: resolve_symbol (fuzzy match).

list_symbols / scan_trending / list_categories are exposed as
@mcp.resource, not tools — see src/cryptozavr/mcp/resources/.
"""

from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.dependencies import Depends
from pydantic import Field

from cryptozavr.application.services.symbol_resolver import SymbolResolver
from cryptozavr.domain.exceptions import DomainError
from cryptozavr.mcp.dtos import SymbolDTO
from cryptozavr.mcp.errors import domain_to_tool_error
from cryptozavr.mcp.lifespan_state import get_symbol_resolver

_RESOLVER: SymbolResolver = Depends(get_symbol_resolver)


def register_resolve_symbol_tool(mcp: FastMCP) -> None:
    """Attach resolve_symbol tool to the given FastMCP instance."""

    @mcp.tool(
        name="resolve_symbol",
        description=(
            "Fuzzy-match a user's symbol string (e.g. 'btc', 'BTCUSDT', "
            "'BTC-USDT') against the SymbolRegistry for a venue. "
            "Useful when the user gives a casual ticker form."
        ),
        tags={"discovery", "public", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def resolve_symbol(
        user_input: Annotated[
            str,
            Field(description="Any user string (btc, BTCUSDT, BTC-USDT)."),
        ],
        venue: Annotated[
            str,
            Field(description="Venue id: kucoin, coingecko."),
        ],
        ctx: Context,
        resolver: SymbolResolver = _RESOLVER,
    ) -> SymbolDTO:
        await ctx.info(
            f"resolve_symbol user_input={user_input!r} venue={venue}",
        )
        try:
            symbol = resolver.resolve(user_input=user_input, venue=venue)
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc
        await ctx.info(
            f"resolved → {symbol.native_symbol} (base={symbol.base} quote={symbol.quote})",
        )
        return SymbolDTO.from_domain(symbol)
