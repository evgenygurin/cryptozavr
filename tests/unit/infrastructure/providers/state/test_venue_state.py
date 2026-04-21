"""Test minimal VenueState context (M2.3a)."""

from __future__ import annotations

import pytest

from cryptozavr.domain.exceptions import ProviderUnavailableError
from cryptozavr.domain.venues import VenueId, VenueStateKind
from cryptozavr.infrastructure.providers.state.venue_state import VenueState


class TestVenueState:
    def test_default_is_healthy(self) -> None:
        state = VenueState(venue_id=VenueId.KUCOIN)
        assert state.kind == VenueStateKind.HEALTHY
        assert state.venue_id == VenueId.KUCOIN

    def test_can_initialize_with_kind(self) -> None:
        state = VenueState(venue_id=VenueId.KUCOIN, kind=VenueStateKind.DEGRADED)
        assert state.kind == VenueStateKind.DEGRADED

    def test_require_operational_healthy_passes(self) -> None:
        state = VenueState(venue_id=VenueId.KUCOIN)
        state.require_operational()

    def test_require_operational_degraded_passes(self) -> None:
        state = VenueState(venue_id=VenueId.KUCOIN, kind=VenueStateKind.DEGRADED)
        state.require_operational()

    def test_require_operational_rate_limited_raises(self) -> None:
        state = VenueState(
            venue_id=VenueId.KUCOIN,
            kind=VenueStateKind.RATE_LIMITED,
        )
        with pytest.raises(ProviderUnavailableError, match="rate_limited"):
            state.require_operational()

    def test_require_operational_down_raises(self) -> None:
        state = VenueState(venue_id=VenueId.KUCOIN, kind=VenueStateKind.DOWN)
        with pytest.raises(ProviderUnavailableError, match="down"):
            state.require_operational()

    def test_transition_updates_kind(self) -> None:
        state = VenueState(venue_id=VenueId.KUCOIN)
        state.transition_to(VenueStateKind.DEGRADED)
        assert state.kind == VenueStateKind.DEGRADED
        state.transition_to(VenueStateKind.DOWN)
        assert state.kind == VenueStateKind.DOWN
