"""State pattern handlers: one class per VenueStateKind.

VenueState (context) holds the current handler and delegates on_* events.
Handlers return a new handler instance when transition is warranted.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from cryptozavr.domain.exceptions import (
    ProviderUnavailableError,
    RateLimitExceededError,
)
from cryptozavr.domain.venues import VenueStateKind

_ERRORS_BEFORE_DEGRADED: int = 3
_SUCCESSES_BEFORE_HEALTHY: int = 5


@dataclass
class _TransitionContext:
    error_count: int
    success_streak: int


class StateHandler:
    """Base: default no-op behaviour."""

    kind: VenueStateKind = VenueStateKind.HEALTHY

    def on_request_started(
        self,
        ctx: _TransitionContext,
    ) -> StateHandler | None:
        return None

    def on_request_succeeded(
        self,
        ctx: _TransitionContext,
    ) -> StateHandler | None:
        return None

    def on_request_failed(
        self,
        exc: Exception,
        ctx: _TransitionContext,
    ) -> StateHandler | None:
        return None

    def check_operational(self) -> None:
        return None


class HealthyStateHandler(StateHandler):
    kind = VenueStateKind.HEALTHY

    def on_request_failed(
        self,
        exc: Exception,
        ctx: _TransitionContext,
    ) -> StateHandler | None:
        if isinstance(exc, RateLimitExceededError):
            return RateLimitedStateHandler(cooldown_sec=30)
        if ctx.error_count >= _ERRORS_BEFORE_DEGRADED:
            return DegradedStateHandler()
        return None


class DegradedStateHandler(StateHandler):
    kind = VenueStateKind.DEGRADED

    def on_request_succeeded(
        self,
        ctx: _TransitionContext,
    ) -> StateHandler | None:
        if ctx.success_streak >= _SUCCESSES_BEFORE_HEALTHY:
            return HealthyStateHandler()
        return None

    def on_request_failed(
        self,
        exc: Exception,
        ctx: _TransitionContext,
    ) -> StateHandler | None:
        if isinstance(exc, RateLimitExceededError):
            return RateLimitedStateHandler(cooldown_sec=30)
        return None


class RateLimitedStateHandler(StateHandler):
    kind = VenueStateKind.RATE_LIMITED

    def __init__(self, *, cooldown_sec: int) -> None:
        self._cooldown_until = time.monotonic() + cooldown_sec

    def on_request_started(
        self,
        ctx: _TransitionContext,
    ) -> StateHandler | None:
        if time.monotonic() >= self._cooldown_until:
            return HealthyStateHandler()
        return None

    def check_operational(self) -> None:
        if time.monotonic() < self._cooldown_until:
            raise ProviderUnavailableError("venue is rate_limited")


class DownStateHandler(StateHandler):
    kind = VenueStateKind.DOWN

    def check_operational(self) -> None:
        raise ProviderUnavailableError("venue is down")
