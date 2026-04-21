"""VenueState: minimal context for M2.3a.

Full State pattern (HealthyState/DegradedState/RateLimitedState/DownState classes
with on_request_succeeded / on_request_failed transitions) arrives in M2.3b.
"""

from __future__ import annotations

from cryptozavr.domain.exceptions import ProviderUnavailableError
from cryptozavr.domain.venues import VenueId, VenueStateKind


class VenueState:
    """Tracks a venue's operational state. Used by BaseProvider._execute."""

    def __init__(
        self,
        venue_id: VenueId,
        *,
        kind: VenueStateKind = VenueStateKind.HEALTHY,
    ) -> None:
        self.venue_id = venue_id
        self._kind = kind

    @property
    def kind(self) -> VenueStateKind:
        return self._kind

    def transition_to(self, new_kind: VenueStateKind) -> None:
        """Force-transition to a new state. M2.3b adds transition rules."""
        self._kind = new_kind

    def require_operational(self) -> None:
        """Raise ProviderUnavailableError if the venue is not usable."""
        if self._kind == VenueStateKind.RATE_LIMITED:
            raise ProviderUnavailableError(f"venue {self.venue_id.value} is rate_limited")
        if self._kind == VenueStateKind.DOWN:
            raise ProviderUnavailableError(f"venue {self.venue_id.value} is down")
