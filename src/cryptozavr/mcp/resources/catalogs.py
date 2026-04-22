"""Catalog resources: venues, symbols-per-venue, discovery.

All resources return `ResourceResult(ResourceContent(..., mime_type="application/json"))`
— v3 idiomatic explicit-MIME form. Needed because FastMCP template resources
lose the decorator-level `mime_type` hint under stdio transport, so clients
see `text/plain` despite the decorator kwarg. See FastMCP docs
`servers/resources.mdx#resourceresult`.
"""

import json

from fastmcp import FastMCP
from fastmcp.dependencies import Depends
from fastmcp.resources import ResourceContent, ResourceResult

from cryptozavr.application.services.discovery_service import DiscoveryService
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import VenueId
from cryptozavr.mcp.dtos import CategoryDTO, TrendingAssetDTO
from cryptozavr.mcp.lifespan_state import get_discovery_service, get_registry

_REGISTRY: SymbolRegistry = Depends(get_registry)
_DISCOVERY: DiscoveryService = Depends(get_discovery_service)

_JSON_MIME = "application/json"


def _json_resource(payload: object) -> ResourceResult:
    """Wrap a JSON-serialisable payload in a single-content JSON ResourceResult."""
    return ResourceResult(
        contents=[
            ResourceContent(
                content=json.dumps(payload),
                mime_type=_JSON_MIME,
            ),
        ],
    )


def register_resources(mcp: FastMCP) -> None:
    """Attach catalog resources to the given FastMCP instance."""

    @mcp.resource(
        "cryptozavr://venues",
        name="Supported Venues",
        description="List of venue ids the plugin can serve.",
        mime_type=_JSON_MIME,
        tags={"catalog"},
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    def venues_resource() -> ResourceResult:
        return _json_resource({"venues": sorted(v.value for v in VenueId)})

    @mcp.resource(
        "cryptozavr://symbols/{venue}",
        name="Symbols for Venue",
        description="All registered symbols on a venue.",
        mime_type=_JSON_MIME,
        tags={"catalog"},
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    def symbols_resource(
        venue: str,
        registry: SymbolRegistry = _REGISTRY,
    ) -> ResourceResult:
        try:
            venue_id = VenueId(venue)
        except ValueError:
            return _json_resource(
                {"venue": venue, "symbols": [], "error": "unsupported"},
            )
        symbols = registry.all_for_venue(venue_id)
        return _json_resource(
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
        mime_type=_JSON_MIME,
        tags={"catalog", "discovery"},
        annotations={"readOnlyHint": True, "idempotentHint": False},
    )
    async def trending_resource(
        discovery: DiscoveryService = _DISCOVERY,
    ) -> ResourceResult:
        try:
            assets = await discovery.list_trending()
        except Exception as exc:
            return _json_resource({"assets": [], "error": str(exc)})
        return _json_resource(
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
        mime_type=_JSON_MIME,
        tags={"catalog", "discovery"},
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    async def categories_resource(
        discovery: DiscoveryService = _DISCOVERY,
    ) -> ResourceResult:
        try:
            raw = await discovery.list_categories()
        except Exception as exc:
            return _json_resource({"categories": [], "error": str(exc)})
        return _json_resource(
            {
                "categories": [CategoryDTO.from_provider(c).model_dump(mode="json") for c in raw],
            },
        )
