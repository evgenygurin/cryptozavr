"""HealthMonitor: periodically probes venues and updates VenueState + metrics."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

from cryptozavr.domain.exceptions import RateLimitExceededError
from cryptozavr.domain.venues import VenueId
from cryptozavr.infrastructure.observability.metrics import MetricsRegistry
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

HealthProbe = Callable[[], Awaitable[None]]

_METRIC_NAME = "venue_health_check_total"


class HealthMonitor:
    """Loops over `probes`, applies outcome to `states`, records metrics.

    Uses the same outcome classification as MetricsDecorator:
    ok / rate_limited / timeout / error.
    """

    def __init__(
        self,
        *,
        probes: dict[VenueId, HealthProbe],
        states: dict[VenueId, VenueState],
        metrics: MetricsRegistry,
        interval_seconds: float = 60.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self._probes = probes
        self._states = states
        self._metrics = metrics
        self._interval = interval_seconds
        self._logger = logger or logging.getLogger("cryptozavr.application.health_monitor")
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def check_once(self) -> None:
        for venue_id, probe in self._probes.items():
            outcome = await self._run_probe(venue_id, probe)
            self._metrics.inc_counter(
                _METRIC_NAME,
                labels={"venue": str(venue_id), "outcome": outcome},
            )

    async def _run_probe(self, venue_id: VenueId, probe: HealthProbe) -> str:
        state = self._states.get(venue_id)
        if state is not None:
            state.mark_probe_performed(int(time.time() * 1000))
        try:
            await probe()
        except RateLimitExceededError as exc:
            self._logger.warning("health probe rate-limited on %s: %s", venue_id, exc)
            if state is not None:
                state.on_request_failed(exc)
            return "rate_limited"
        except TimeoutError as exc:
            self._logger.warning("health probe timed out on %s", venue_id)
            if state is not None:
                state.on_request_failed(exc)
            return "timeout"
        except Exception as exc:
            self._logger.warning("health probe failed on %s: %s", venue_id, exc)
            if state is not None:
                state.on_request_failed(exc)
            return "error"
        if state is not None:
            state.on_request_succeeded()
        return "ok"

    async def start(self) -> None:
        if self.is_running:
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._run_forever(), name="cryptozavr-health-monitor")

    async def stop(self) -> None:
        self._stopping.set()
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            self._logger.exception("health monitor task raised during shutdown")

    async def _run_forever(self) -> None:
        while not self._stopping.is_set():
            try:
                await self.check_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                self._logger.exception("health monitor iteration crashed")
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
            except TimeoutError:
                continue
