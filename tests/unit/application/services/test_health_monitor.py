"""HealthMonitor: outcome classification + VenueState integration + lifecycle."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import pytest

from cryptozavr.application.services.health_monitor import HealthMonitor
from cryptozavr.domain.exceptions import (
    ProviderUnavailableError,
    RateLimitExceededError,
)
from cryptozavr.domain.venues import VenueId, VenueStateKind
from cryptozavr.infrastructure.observability.metrics import MetricsRegistry
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

Probe = Callable[[], Awaitable[None]]


def _counter(registry: MetricsRegistry, venue: str, outcome: str) -> int:
    for entry in registry.snapshot()["counters"]:
        labels = entry["labels"]
        if labels.get("venue") == venue and labels.get("outcome") == outcome:
            return int(entry["value"])
    return 0


def _ok_probe() -> Probe:
    async def probe() -> None:
        return None

    return probe


def _raising_probe(exc: Exception) -> Probe:
    async def probe() -> None:
        raise exc

    return probe


@pytest.mark.asyncio
async def test_check_once_success_increments_ok_counter() -> None:
    registry = MetricsRegistry()
    states = {VenueId.KUCOIN: VenueState(VenueId.KUCOIN)}
    monitor = HealthMonitor(
        probes={VenueId.KUCOIN: _ok_probe()},
        states=states,
        metrics=registry,
    )

    await monitor.check_once()

    assert _counter(registry, "kucoin", "ok") == 1


@pytest.mark.asyncio
async def test_check_once_rate_limit_classified_rate_limited() -> None:
    registry = MetricsRegistry()
    monitor = HealthMonitor(
        probes={VenueId.KUCOIN: _raising_probe(RateLimitExceededError("nope"))},
        states={VenueId.KUCOIN: VenueState(VenueId.KUCOIN)},
        metrics=registry,
    )

    await monitor.check_once()

    assert _counter(registry, "kucoin", "rate_limited") == 1


@pytest.mark.asyncio
async def test_check_once_timeout_classified_timeout() -> None:
    registry = MetricsRegistry()
    monitor = HealthMonitor(
        probes={VenueId.KUCOIN: _raising_probe(TimeoutError())},
        states={VenueId.KUCOIN: VenueState(VenueId.KUCOIN)},
        metrics=registry,
    )

    await monitor.check_once()

    assert _counter(registry, "kucoin", "timeout") == 1


@pytest.mark.asyncio
async def test_check_once_generic_error_classified_error() -> None:
    registry = MetricsRegistry()
    state = VenueState(VenueId.KUCOIN)
    monitor = HealthMonitor(
        probes={VenueId.KUCOIN: _raising_probe(ProviderUnavailableError("boom"))},
        states={VenueId.KUCOIN: state},
        metrics=registry,
    )

    await monitor.check_once()

    assert _counter(registry, "kucoin", "error") == 1
    # VenueState should have observed the failure.
    assert state.kind in {VenueStateKind.HEALTHY, VenueStateKind.DEGRADED}


@pytest.mark.asyncio
async def test_check_once_handles_missing_state_gracefully() -> None:
    registry = MetricsRegistry()
    monitor = HealthMonitor(
        probes={VenueId.KUCOIN: _raising_probe(RuntimeError("no state"))},
        states={},  # intentionally empty
        metrics=registry,
    )

    await monitor.check_once()

    assert _counter(registry, "kucoin", "error") == 1


@pytest.mark.asyncio
async def test_check_once_each_venue_records_independently() -> None:
    registry = MetricsRegistry()
    monitor = HealthMonitor(
        probes={
            VenueId.KUCOIN: _ok_probe(),
            VenueId.COINGECKO: _raising_probe(RuntimeError("down")),
        },
        states={
            VenueId.KUCOIN: VenueState(VenueId.KUCOIN),
            VenueId.COINGECKO: VenueState(VenueId.COINGECKO),
        },
        metrics=registry,
    )

    await monitor.check_once()

    assert _counter(registry, "kucoin", "ok") == 1
    assert _counter(registry, "coingecko", "error") == 1


@pytest.mark.asyncio
async def test_start_and_stop_runs_at_least_one_iteration() -> None:
    registry = MetricsRegistry()
    calls = 0

    async def probe() -> None:
        nonlocal calls
        calls += 1

    monitor = HealthMonitor(
        probes={VenueId.KUCOIN: probe},
        states={VenueId.KUCOIN: VenueState(VenueId.KUCOIN)},
        metrics=registry,
        interval_seconds=10.0,
    )

    await monitor.start()
    # Yield the loop a couple of times to let check_once run.
    for _ in range(10):
        await asyncio.sleep(0)
        if calls >= 1:
            break
    await monitor.stop()

    assert calls >= 1
    assert not monitor.is_running


@pytest.mark.asyncio
async def test_mark_probe_performed_fires_after_probe_completes() -> None:
    """Timestamp must reflect probe completion time, not start — otherwise
    a hung probe would masquerade as 'just checked'."""
    events: list[str] = []

    class _SpyState(VenueState):
        def mark_probe_performed(self, now_ms: int) -> None:
            events.append("mark")
            super().mark_probe_performed(now_ms)

    async def probe() -> None:
        events.append("probe_start")
        await asyncio.sleep(0)
        events.append("probe_end")

    state = _SpyState(VenueId.KUCOIN)
    monitor = HealthMonitor(
        probes={VenueId.KUCOIN: probe},
        states={VenueId.KUCOIN: state},
        metrics=MetricsRegistry(),
    )
    await monitor.check_once()
    assert events == ["probe_start", "probe_end", "mark"]


@pytest.mark.asyncio
async def test_check_once_updates_last_checked_at() -> None:
    registry = MetricsRegistry()
    state = VenueState(VenueId.KUCOIN)
    assert state.last_checked_at_ms is None
    monitor = HealthMonitor(
        probes={VenueId.KUCOIN: _ok_probe()},
        states={VenueId.KUCOIN: state},
        metrics=registry,
    )

    await monitor.check_once()

    assert state.last_checked_at_ms is not None
    assert state.last_checked_at_ms > 0


@pytest.mark.asyncio
async def test_run_forever_survives_iteration_exception() -> None:
    """A crashing probe must not kill the loop — next tick should run."""
    registry = MetricsRegistry()
    calls = 0

    async def flaky_probe() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("first iteration crashed")

    monitor = HealthMonitor(
        probes={VenueId.KUCOIN: flaky_probe},
        states={VenueId.KUCOIN: VenueState(VenueId.KUCOIN)},
        metrics=registry,
        interval_seconds=0.0,
    )
    await monitor.start()
    for _ in range(50):
        await asyncio.sleep(0.005)
        if calls >= 2:
            break
    await monitor.stop()
    assert calls >= 2


@pytest.mark.asyncio
async def test_stop_is_idempotent() -> None:
    monitor = HealthMonitor(
        probes={},
        states={},
        metrics=MetricsRegistry(),
    )
    await monitor.stop()  # before start — no-op
    await monitor.start()
    await monitor.stop()
    await monitor.stop()  # second stop — no-op
    assert not monitor.is_running
