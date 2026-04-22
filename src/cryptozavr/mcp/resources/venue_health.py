"""Venue health resource: current state + last_checked_ms per venue."""

import json

from fastmcp import FastMCP
from fastmcp.dependencies import Depends

from cryptozavr.domain.venues import VenueId, VenueStateKind
from cryptozavr.infrastructure.providers.state.venue_state import VenueState
from cryptozavr.mcp.lifespan_state import get_venue_states

_VENUE_STATES: dict[VenueId, VenueState] = Depends(get_venue_states)


def _label_for(state: VenueState) -> str:
    kind = state.kind
    if kind is VenueStateKind.HEALTHY:
        return "healthy"
    if kind is VenueStateKind.DOWN:
        return "down"
    return "degraded"


def register_venue_health_resource(mcp: FastMCP) -> None:
    """Attach cryptozavr://venue_health resource to the given FastMCP instance."""

    @mcp.resource(
        "cryptozavr://venue_health",
        name="Venue Health",
        description=(
            "Current health label + last_checked_ms per known venue. "
            "Consumed by the SessionStart plugin hook banner."
        ),
        mime_type="application/json",
        tags={"observability"},
        annotations={"readOnlyHint": True, "idempotentHint": False},
    )
    def venue_health_resource(
        venue_states: dict[VenueId, VenueState] = _VENUE_STATES,
    ) -> str:
        return json.dumps(
            {
                "venues": [
                    {
                        "venue": str(venue_id),
                        "state": _label_for(state),
                        "last_checked_ms": state.last_checked_at_ms,
                    }
                    for venue_id, state in venue_states.items()
                ],
            },
        )
