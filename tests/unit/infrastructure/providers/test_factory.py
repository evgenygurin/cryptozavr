"""Test ProviderFactory: wires base provider with decorator chain."""

from __future__ import annotations

import pytest

from cryptozavr.domain.venues import VenueId
from cryptozavr.infrastructure.observability.metrics import MetricsRegistry
from cryptozavr.infrastructure.providers.decorators.caching import (
    InMemoryCachingDecorator,
)
from cryptozavr.infrastructure.providers.decorators.logging import (
    LoggingDecorator,
)
from cryptozavr.infrastructure.providers.decorators.metrics import (
    MetricsDecorator,
)
from cryptozavr.infrastructure.providers.decorators.rate_limit import (
    RateLimitDecorator,
)
from cryptozavr.infrastructure.providers.decorators.retry import RetryDecorator
from cryptozavr.infrastructure.providers.factory import ProviderFactory
from cryptozavr.infrastructure.providers.http import HttpClientRegistry
from cryptozavr.infrastructure.providers.rate_limiters import RateLimiterRegistry
from cryptozavr.infrastructure.providers.state.venue_state import VenueState


class _FakeExchange:
    """Duck-type for ccxt exchange."""

    async def load_markets(self) -> dict:
        return {}

    async def fetch_ticker(self, symbol: str) -> dict:
        return {"last": 1.0, "symbol": symbol}

    async def close(self) -> None:
        return None


@pytest.fixture
def rate_registry() -> RateLimiterRegistry:
    reg = RateLimiterRegistry()
    reg.register("kucoin", rate_per_sec=30.0, capacity=30)
    reg.register("coingecko", rate_per_sec=0.5, capacity=30)
    return reg


@pytest.mark.asyncio
async def test_create_kucoin_returns_wrapped_provider(
    rate_registry: RateLimiterRegistry,
) -> None:
    factory = ProviderFactory(
        http_registry=HttpClientRegistry(),
        rate_registry=rate_registry,
    )
    state = VenueState(VenueId.KUCOIN)
    provider = factory.create_kucoin(state=state, exchange=_FakeExchange())

    # Chain: Logging > Caching > RateLimit > Retry > base
    assert isinstance(provider, LoggingDecorator)
    inner = provider._inner
    assert isinstance(inner, InMemoryCachingDecorator)
    inner2 = inner._inner
    assert isinstance(inner2, RateLimitDecorator)
    inner3 = inner2._inner
    assert isinstance(inner3, RetryDecorator)


@pytest.mark.asyncio
async def test_create_coingecko_returns_wrapped_provider(
    rate_registry: RateLimiterRegistry,
) -> None:
    http_registry = HttpClientRegistry()
    try:
        factory = ProviderFactory(
            http_registry=http_registry,
            rate_registry=rate_registry,
        )
        state = VenueState(VenueId.COINGECKO)
        provider = await factory.create_coingecko(state=state)
        assert isinstance(provider, LoggingDecorator)
    finally:
        await http_registry.close_all()


@pytest.mark.asyncio
async def test_factory_inserts_metrics_decorator_when_registry_provided(
    rate_registry: RateLimiterRegistry,
) -> None:
    metrics = MetricsRegistry()
    factory = ProviderFactory(
        http_registry=HttpClientRegistry(),
        rate_registry=rate_registry,
        metrics_registry=metrics,
    )
    state = VenueState(VenueId.KUCOIN)
    provider = factory.create_kucoin(state=state, exchange=_FakeExchange())

    # Chain: Logging > Caching > RateLimit > Retry > Metrics > base
    retry = provider._inner._inner._inner
    assert isinstance(retry, RetryDecorator)
    assert isinstance(retry._inner, MetricsDecorator)

    # A successful load_markets should bump the Prometheus counter.
    await provider.load_markets()
    snap = metrics.snapshot()
    assert any(
        c["name"] == "provider_calls_total"
        and c["labels"].get("endpoint") == "load_markets"
        and c["labels"].get("outcome") == "ok"
        for c in snap["counters"]
    )


@pytest.mark.asyncio
async def test_factory_uses_configured_ttls(
    rate_registry: RateLimiterRegistry,
) -> None:
    http_registry = HttpClientRegistry()
    try:
        factory = ProviderFactory(
            http_registry=http_registry,
            rate_registry=rate_registry,
            ticker_ttl=2.0,
            ohlcv_ttl=30.0,
        )
        state = VenueState(VenueId.KUCOIN)
        provider = factory.create_kucoin(state=state, exchange=_FakeExchange())
        # Dig into caching decorator
        caching = provider._inner
        assert caching._ticker_ttl == 2.0
        assert caching._ohlcv_ttl == 30.0
    finally:
        await http_registry.close_all()
