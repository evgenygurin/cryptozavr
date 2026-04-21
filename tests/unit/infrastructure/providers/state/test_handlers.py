"""Per-handler tests: each handler reports the right VenueStateKind."""

from __future__ import annotations

from cryptozavr.domain.venues import VenueStateKind
from cryptozavr.infrastructure.providers.state.handlers import (
    DegradedStateHandler,
    DownStateHandler,
    HealthyStateHandler,
    RateLimitedStateHandler,
)


def test_healthy_kind() -> None:
    assert HealthyStateHandler().kind == VenueStateKind.HEALTHY


def test_degraded_kind() -> None:
    assert DegradedStateHandler().kind == VenueStateKind.DEGRADED


def test_rate_limited_kind() -> None:
    assert RateLimitedStateHandler(cooldown_sec=30).kind == VenueStateKind.RATE_LIMITED


def test_down_kind() -> None:
    assert DownStateHandler().kind == VenueStateKind.DOWN
