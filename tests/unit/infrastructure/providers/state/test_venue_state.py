"""Test minimal VenueState context (M2.3a)."""

from __future__ import annotations

import pytest

from cryptozavr.domain.exceptions import ProviderUnavailableError, RateLimitExceededError
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
        state = VenueState(venue_id=VenueId.KUCOIN)
        state.on_request_failed(RateLimitExceededError("429"))
        assert state.kind == VenueStateKind.RATE_LIMITED
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

    def test_last_checked_at_ms_starts_none(self) -> None:
        state = VenueState(venue_id=VenueId.KUCOIN)
        assert state.last_checked_at_ms is None

    def test_mark_probe_performed_updates_timestamp(self) -> None:
        state = VenueState(venue_id=VenueId.KUCOIN)
        state.mark_probe_performed(1_700_000_000_000)
        assert state.last_checked_at_ms == 1_700_000_000_000
        state.mark_probe_performed(1_700_000_060_000)
        assert state.last_checked_at_ms == 1_700_000_060_000


class TestTransitions:
    def test_healthy_degrades_after_3_errors(self) -> None:
        state = VenueState(venue_id=VenueId.KUCOIN)
        for _ in range(3):
            state.on_request_failed(Exception("boom"))
        assert state.kind == VenueStateKind.DEGRADED

    def test_degraded_recovers_after_5_successes(self) -> None:
        state = VenueState(
            venue_id=VenueId.KUCOIN,
            kind=VenueStateKind.DEGRADED,
        )
        for _ in range(5):
            state.on_request_succeeded()
        assert state.kind == VenueStateKind.HEALTHY

    def test_rate_limit_error_transitions_to_rate_limited(self) -> None:
        state = VenueState(venue_id=VenueId.KUCOIN)
        state.on_request_failed(RateLimitExceededError("429"))
        assert state.kind == VenueStateKind.RATE_LIMITED

    def test_rate_limited_expires_back_to_healthy_after_cooldown(self) -> None:
        # Note: can't use freeze_time easily because RateLimitedStateHandler
        # uses time.monotonic(). Test that the handler logic works by patching.
        state = VenueState(venue_id=VenueId.KUCOIN)
        state.on_request_failed(RateLimitExceededError("429"))
        assert state.kind == VenueStateKind.RATE_LIMITED

        # Force cooldown to have already passed by mutating the handler
        state._handler._cooldown_until = 0.0  # type: ignore[union-attr]
        state.on_request_started()
        assert state.kind == VenueStateKind.HEALTHY

    def test_mark_down_forces_down_state(self) -> None:
        state = VenueState(venue_id=VenueId.KUCOIN)
        state.mark_down()
        assert state.kind == VenueStateKind.DOWN
        with pytest.raises(ProviderUnavailableError):
            state.require_operational()

    def test_success_resets_error_count(self) -> None:
        state = VenueState(venue_id=VenueId.KUCOIN)
        state.on_request_failed(Exception("boom"))
        state.on_request_failed(Exception("boom"))
        state.on_request_succeeded()
        state.on_request_failed(Exception("boom"))
        state.on_request_failed(Exception("boom"))
        assert state.kind == VenueStateKind.HEALTHY
        state.on_request_failed(Exception("boom"))
        assert state.kind == VenueStateKind.DEGRADED
