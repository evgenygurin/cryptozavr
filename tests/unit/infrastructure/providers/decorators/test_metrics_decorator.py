"""MetricsDecorator: outcome classification + duration histogram."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from cryptozavr.domain.exceptions import (
    ProviderUnavailableError,
    RateLimitExceededError,
)
from cryptozavr.infrastructure.observability.metrics import MetricsRegistry
from cryptozavr.infrastructure.providers.decorators.metrics import (
    MetricsDecorator,
)


class _StubProvider:
    venue_id = "kucoin"

    def __init__(self, *, exc: Exception | None = None) -> None:
        self._exc = exc
        self.calls = 0

    async def load_markets(self) -> None:
        return None

    async def fetch_ticker(self, symbol: Any) -> str:
        self.calls += 1
        if self._exc is not None:
            raise self._exc
        return f"ticker-{symbol}"

    async def fetch_ohlcv(self, *args: object, **kwargs: object) -> object:
        raise NotImplementedError

    async def fetch_order_book(self, *args: object, **kwargs: object) -> object:
        raise NotImplementedError

    async def fetch_trades(self, *args: object, **kwargs: object) -> object:
        raise NotImplementedError

    async def close(self) -> None:
        return None


def _counter_value(registry: MetricsRegistry, outcome: str) -> int:
    for entry in registry.snapshot()["counters"]:
        if entry["labels"].get("outcome") == outcome:
            return int(entry["value"])
    return 0


@pytest.mark.asyncio
async def test_successful_call_records_ok_outcome() -> None:
    reg = MetricsRegistry()
    dec = MetricsDecorator(_StubProvider(), registry=reg)  # type: ignore[arg-type]

    result = await dec.fetch_ticker("BTC/USDT")

    assert result == "ticker-BTC/USDT"
    assert _counter_value(reg, "ok") == 1


@pytest.mark.asyncio
async def test_rate_limit_error_marked_rate_limited() -> None:
    reg = MetricsRegistry()
    dec = MetricsDecorator(
        _StubProvider(exc=RateLimitExceededError("nope")),  # type: ignore[arg-type]
        registry=reg,
    )

    with pytest.raises(RateLimitExceededError):
        await dec.fetch_ticker("BTC/USDT")

    assert _counter_value(reg, "rate_limited") == 1


@pytest.mark.asyncio
async def test_timeout_marked_timeout() -> None:
    reg = MetricsRegistry()
    dec = MetricsDecorator(
        _StubProvider(exc=TimeoutError()),  # type: ignore[arg-type]
        registry=reg,
    )

    with pytest.raises((asyncio.TimeoutError, TimeoutError)):
        await dec.fetch_ticker("BTC/USDT")

    assert _counter_value(reg, "timeout") == 1


@pytest.mark.asyncio
async def test_other_exception_marked_error() -> None:
    reg = MetricsRegistry()
    dec = MetricsDecorator(
        _StubProvider(exc=ProviderUnavailableError("boom")),  # type: ignore[arg-type]
        registry=reg,
    )

    with pytest.raises(ProviderUnavailableError):
        await dec.fetch_ticker("BTC/USDT")

    assert _counter_value(reg, "error") == 1


@pytest.mark.asyncio
async def test_histogram_duration_recorded() -> None:
    reg = MetricsRegistry()
    dec = MetricsDecorator(_StubProvider(), registry=reg)  # type: ignore[arg-type]

    await dec.fetch_ticker("BTC/USDT")

    hist = reg.snapshot()["histograms"]
    assert len(hist) == 1
    entry = hist[0]
    assert entry["labels"] == {"venue": "kucoin", "endpoint": "fetch_ticker"}
    assert entry["count"] == 1
    assert entry["sum"] >= 0.0


@pytest.mark.asyncio
async def test_venue_id_forwarded() -> None:
    dec = MetricsDecorator(
        _StubProvider(),  # type: ignore[arg-type]
        registry=MetricsRegistry(),
    )
    assert dec.venue_id == "kucoin"


@pytest.mark.asyncio
async def test_unknown_attribute_forwarded_via_getattr() -> None:
    provider = _StubProvider()
    dec = MetricsDecorator(provider, registry=MetricsRegistry())  # type: ignore[arg-type]
    assert dec.calls == 0
    await dec.fetch_ticker("X/Y")
    assert dec.calls == 1
