"""VenueState: State pattern context delegating to handlers."""

from __future__ import annotations

from cryptozavr.domain.venues import VenueId, VenueStateKind
from cryptozavr.infrastructure.providers.state.handlers import (
    DegradedStateHandler,
    DownStateHandler,
    HealthyStateHandler,
    StateHandler,
    _TransitionContext,
)

_INITIAL_HANDLERS: dict[VenueStateKind, type[StateHandler]] = {
    VenueStateKind.HEALTHY: HealthyStateHandler,
    VenueStateKind.DEGRADED: DegradedStateHandler,
    VenueStateKind.DOWN: DownStateHandler,
}


class VenueState:
    """Context: holds current handler + transition state (error/success counters)."""

    def __init__(
        self,
        venue_id: VenueId,
        *,
        kind: VenueStateKind = VenueStateKind.HEALTHY,
    ) -> None:
        self.venue_id = venue_id
        cls = _INITIAL_HANDLERS.get(kind)
        if cls is None:
            raise ValueError(
                f"cannot initialize VenueState with kind={kind}; "
                "use default or one of HEALTHY/DEGRADED/DOWN"
            )
        self._handler: StateHandler = cls()
        self._ctx = _TransitionContext(error_count=0, success_streak=0)

    @property
    def kind(self) -> VenueStateKind:
        return self._handler.kind

    def require_operational(self) -> None:
        self._handler.check_operational()

    def transition_to(self, new_kind: VenueStateKind) -> None:
        """Backward-compat helper. Prefer on_request_*."""
        cls = _INITIAL_HANDLERS.get(new_kind)
        if cls is None:
            raise ValueError(f"transition_to cannot create {new_kind} directly")
        self._handler = cls()
        self._reset_counters()

    def mark_down(self) -> None:
        self._handler = DownStateHandler()
        self._reset_counters()

    def on_request_started(self) -> None:
        new = self._handler.on_request_started(self._ctx)
        if new is not None:
            self._handler = new
            self._reset_counters()

    def on_request_succeeded(self) -> None:
        self._ctx.success_streak += 1
        self._ctx.error_count = 0
        new = self._handler.on_request_succeeded(self._ctx)
        if new is not None:
            self._handler = new
            self._reset_counters()

    def on_request_failed(self, exc: Exception) -> None:
        self._ctx.error_count += 1
        self._ctx.success_streak = 0
        new = self._handler.on_request_failed(exc, self._ctx)
        if new is not None:
            self._handler = new
            self._reset_counters()

    def _reset_counters(self) -> None:
        self._ctx.error_count = 0
        self._ctx.success_streak = 0
