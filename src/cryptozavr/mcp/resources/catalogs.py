"""Catalog resources: venues, symbols-per-venue."""

import json

from fastmcp import FastMCP
from fastmcp.dependencies import Depends

from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import VenueId
from cryptozavr.mcp.lifespan_state import get_registry

_REGISTRY: SymbolRegistry = Depends(get_registry)


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
