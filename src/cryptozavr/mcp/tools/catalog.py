"""Catalog tools: Pydantic-DTO returns so MCP clients get `structuredContent`.

Resources (`cryptozavr://...`) are still exposed and cacheable, but their
wire format forces `TextResourceContents.text = str`, which means any
nested JSON is escaped. These tools mirror the same data but return
Pydantic models — FastMCP v3 auto-populates `CallToolResult.structuredContent`
so clients render native objects instead of escaped strings.
"""

from __future__ import annotations

from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.dependencies import Depends
from pydantic import Field

from cryptozavr.application.services.discovery_service import DiscoveryService
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId, VenueStateKind
from cryptozavr.infrastructure.providers.state.venue_state import VenueState
from cryptozavr.mcp.dtos import (
    CategoriesListDTO,
    CategoryDTO,
    SymbolDTO,
    SymbolsListDTO,
    TrendingAssetDTO,
    TrendingListDTO,
    VenueHealthDTO,
    VenueHealthEntryDTO,
    VenuesListDTO,
)
from cryptozavr.mcp.lifespan_state import (
    get_discovery_service,
    get_providers,
    get_registry,
    get_venue_states,
)

_REGISTRY: SymbolRegistry = Depends(get_registry)
_DISCOVERY: DiscoveryService = Depends(get_discovery_service)
_VENUE_STATES: dict[VenueId, VenueState] = Depends(get_venue_states)
_PROVIDERS: dict[VenueId, object] = Depends(get_providers)


def _venue_state_label(state: VenueState) -> str:
    kind = state.kind
    if kind is VenueStateKind.HEALTHY:
        return "healthy"
    if kind is VenueStateKind.DOWN:
        return "down"
    return "degraded"


def register_catalog_tools(mcp: FastMCP) -> None:
    """Attach list_venues/list_symbols/list_trending/list_categories/get_venue_health."""

    @mcp.tool(
        name="list_venues",
        description="List all venue ids the plugin can serve.",
        tags={"catalog", "read-only"},
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    async def list_venues(ctx: Context) -> VenuesListDTO:
        await ctx.info("list_venues")
        return VenuesListDTO(venues=sorted(v.value for v in VenueId))

    @mcp.tool(
        name="list_symbols",
        description=(
            "Live catalogue of spot symbols on a venue. For `kucoin` this "
            "queries ccxt markets and returns every active spot/USDT pair "
            "(~1000 tokens). For `coingecko` returns what the plugin has "
            "registered locally. No whitelist — any BASE-QUOTE also works "
            "via auto-register in SymbolResolver."
        ),
        tags={"catalog", "read-only"},
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    async def list_symbols(
        venue: Annotated[
            str,
            Field(description="Venue id. Supported: kucoin, coingecko."),
        ],
        ctx: Context,
        quote: Annotated[
            str,
            Field(description="Quote currency filter for live fetch (default USDT)."),
        ] = "USDT",
        registry: SymbolRegistry = _REGISTRY,
        providers: dict[VenueId, object] = _PROVIDERS,
    ) -> SymbolsListDTO:
        await ctx.info(f"list_symbols venue={venue} quote={quote}")
        try:
            venue_id = VenueId(venue)
        except ValueError:
            return SymbolsListDTO(venue=venue, symbols=[], error="unsupported")

        provider = providers.get(venue_id)
        live_fetch = getattr(provider, "list_spot_markets", None)
        if live_fetch is not None:
            try:
                natives = await live_fetch(quote=quote)
            except Exception as exc:
                await ctx.warning(f"live markets fetch failed: {type(exc).__name__}")
                natives = []
            # Materialise into the Flyweight registry so subsequent
            # resolves are O(1); also keeps DTO builder happy.
            dtos: list[SymbolDTO] = []
            for native in natives:
                if "-" not in native:
                    continue
                base, _, quote_code = native.partition("-")
                if not base or not quote_code:
                    continue
                sym = registry.get(
                    venue_id,
                    base,
                    quote_code,
                    market_type=MarketType.SPOT,
                    native_symbol=native,
                )
                dtos.append(SymbolDTO.from_domain(sym))
            return SymbolsListDTO(venue=venue, symbols=dtos)

        # Fallback: just read the registry (non-ccxt venues like coingecko).
        symbols = registry.all_for_venue(venue_id)
        return SymbolsListDTO(
            venue=venue,
            symbols=[SymbolDTO.from_domain(s) for s in symbols],
        )

    @mcp.tool(
        name="list_trending",
        description="Currently trending crypto assets (CoinGecko).",
        tags={"catalog", "discovery", "read-only"},
        annotations={"readOnlyHint": True, "idempotentHint": False},
    )
    async def list_trending(
        ctx: Context,
        discovery: DiscoveryService = _DISCOVERY,
    ) -> TrendingListDTO:
        await ctx.info("list_trending")
        try:
            assets = await discovery.list_trending()
        except Exception as exc:
            await ctx.warning(f"coingecko trending failed: {type(exc).__name__}")
            return TrendingListDTO(assets=[], error=f"{type(exc).__name__}: upstream unavailable")
        return TrendingListDTO(
            assets=[TrendingAssetDTO.from_domain(a, rank=i) for i, a in enumerate(assets)],
        )

    @mcp.tool(
        name="list_categories",
        description="CoinGecko asset categories with market cap + 24h change.",
        tags={"catalog", "discovery", "read-only"},
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    async def list_categories(
        ctx: Context,
        discovery: DiscoveryService = _DISCOVERY,
    ) -> CategoriesListDTO:
        await ctx.info("list_categories")
        try:
            raw = await discovery.list_categories()
        except Exception as exc:
            await ctx.warning(f"coingecko categories failed: {type(exc).__name__}")
            return CategoriesListDTO(
                categories=[], error=f"{type(exc).__name__}: upstream unavailable"
            )
        return CategoriesListDTO(
            categories=[CategoryDTO.from_provider(c) for c in raw],
        )

    @mcp.tool(
        name="get_venue_health",
        description=(
            "Current health label + last_checked_ms per known venue. "
            "Structured equivalent of cryptozavr://venue_health."
        ),
        tags={"observability", "read-only"},
        annotations={"readOnlyHint": True, "idempotentHint": False},
    )
    async def get_venue_health(
        ctx: Context,
        venue_states: dict[VenueId, VenueState] = _VENUE_STATES,
    ) -> VenueHealthDTO:
        await ctx.info("get_venue_health")
        entries = [
            VenueHealthEntryDTO(
                venue=str(venue_id),
                state=_venue_state_label(state),
                last_checked_ms=state.last_checked_at_ms,
            )
            for venue_id, state in venue_states.items()
        ]
        return VenueHealthDTO(venues=entries)
