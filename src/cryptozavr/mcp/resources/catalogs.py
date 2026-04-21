"""Catalog resources: venues, symbols-per-venue."""

import json

from fastmcp import FastMCP
from fastmcp.dependencies import Depends

from cryptozavr.application.services.discovery_service import DiscoveryService
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import VenueId
from cryptozavr.mcp.dtos import CategoryDTO, TrendingAssetDTO
from cryptozavr.mcp.lifespan_state import get_discovery_service, get_registry

_REGISTRY: SymbolRegistry = Depends(get_registry)
_DISCOVERY: DiscoveryService = Depends(get_discovery_service)


def register_resources(mcp: FastMCP) -> None:
    """Attach catalog resources to the given FastMCP instance."""

    @mcp.resource(
        "cryptozavr://venues",
        name="Supported Venues",
        description="List of venue ids the plugin can serve.",
        mime_type="application/json",
        tags={"catalog"},
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    def venues_resource() -> str:
        return json.dumps({"venues": sorted(v.value for v in VenueId)})

    @mcp.resource(
        "cryptozavr://symbols/{venue}",
        name="Symbols for Venue",
        description="All registered symbols on a venue.",
        mime_type="application/json",
        tags={"catalog"},
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    def symbols_resource(
        venue: str,
        registry: SymbolRegistry = _REGISTRY,
    ) -> str:
        try:
            venue_id = VenueId(venue)
        except ValueError:
            return json.dumps(
                {"venue": venue, "symbols": [], "error": "unsupported"},
            )
        symbols = registry.all_for_venue(venue_id)
        return json.dumps(
            {
                "venue": venue,
                "symbols": [
                    {
                        "base": s.base,
                        "quote": s.quote,
                        "native_symbol": s.native_symbol,
                        "market_type": s.market_type.value,
                    }
                    for s in symbols
                ],
            },
        )

    @mcp.resource(
        "cryptozavr://trending",
        name="Trending Assets",
        description=(
            "Currently trending crypto assets (CoinGecko). Ordered by trending rank (0-indexed)."
        ),
        mime_type="application/json",
        tags={"catalog", "discovery"},
        annotations={"readOnlyHint": True, "idempotentHint": False},
    )
    async def trending_resource(
        discovery: DiscoveryService = _DISCOVERY,
    ) -> str:
        try:
            assets = await discovery.list_trending()
        except Exception as exc:
            return json.dumps({"assets": [], "error": str(exc)})
        return json.dumps(
            {
                "assets": [
                    TrendingAssetDTO.from_domain(a, rank=i).model_dump(
                        mode="json",
                    )
                    for i, a in enumerate(assets)
                ],
            },
        )

    @mcp.resource(
        "cryptozavr://categories",
        name="Market Categories",
        description=("CoinGecko asset categories with market cap + 24h change."),
        mime_type="application/json",
        tags={"catalog", "discovery"},
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    async def categories_resource(
        discovery: DiscoveryService = _DISCOVERY,
    ) -> str:
        try:
            raw = await discovery.list_categories()
        except Exception as exc:
            return json.dumps({"categories": [], "error": str(exc)})
        return json.dumps(
            {
                "categories": [CategoryDTO.from_provider(c).model_dump(mode="json") for c in raw],
            },
        )
