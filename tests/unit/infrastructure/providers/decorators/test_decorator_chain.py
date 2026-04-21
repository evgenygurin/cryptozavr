"""Test decorator chain composition: Logging > Caching > RateLimit > Retry > Base."""

from __future__ import annotations

import pytest

from cryptozavr.domain.exceptions import ProviderUnavailableError
from cryptozavr.infrastructure.providers.decorators.caching import (
    InMemoryCachingDecorator,
)
from cryptozavr.infrastructure.providers.decorators.logging import (
    LoggingDecorator,
)
from cryptozavr.infrastructure.providers.decorators.rate_limit import (
    RateLimitDecorator,
)
from cryptozavr.infrastructure.providers.decorators.retry import RetryDecorator
from cryptozavr.infrastructure.providers.rate_limiters import (
    RateLimiterRegistry,
)


class _FlakyProvider:
    venue_id = "kucoin"

    def __init__(self, *, failures: int) -> None:
        self._failures = failures
        self.calls = 0

    async def fetch_ticker(self, symbol: str) -> str:
        self.calls += 1
        if self.calls <= self._failures:
            raise ProviderUnavailableError("flaky")
        return f"ticker-{symbol}"

    async def close(self) -> None:
        pass


@pytest.fixture
def rate_registry() -> RateLimiterRegistry:
    reg = RateLimiterRegistry()
    reg.register("kucoin", rate_per_sec=1000.0, capacity=10)
    return reg


@pytest.mark.asyncio
async def test_full_chain_happy_path(
    rate_registry: RateLimiterRegistry,
) -> None:
    base = _FlakyProvider(failures=0)
    chain = LoggingDecorator(
        InMemoryCachingDecorator(
            RateLimitDecorator(
                RetryDecorator(base, max_attempts=3, base_delay=0.001, jitter=0.0),
                limiter=rate_registry.get("kucoin"),
            ),
            ticker_ttl=60.0,
        ),
    )

    r1 = await chain.fetch_ticker("BTC/USDT")
    r2 = await chain.fetch_ticker("BTC/USDT")  # cache hit
    assert r1 == "ticker-BTC/USDT"
    assert r2 == "ticker-BTC/USDT"
    assert base.calls == 1


@pytest.mark.asyncio
async def test_full_chain_retries_through_flakiness(
    rate_registry: RateLimiterRegistry,
) -> None:
    base = _FlakyProvider(failures=2)
    chain = LoggingDecorator(
        InMemoryCachingDecorator(
            RateLimitDecorator(
                RetryDecorator(base, max_attempts=5, base_delay=0.001, jitter=0.0),
                limiter=rate_registry.get("kucoin"),
            ),
            ticker_ttl=60.0,
        ),
    )
    result = await chain.fetch_ticker("BTC/USDT")
    assert result == "ticker-BTC/USDT"
    assert base.calls == 3  # 2 failures + 1 success
