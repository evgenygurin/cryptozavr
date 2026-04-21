"""Test RateLimitDecorator: acquires token from RateLimiterRegistry."""

from __future__ import annotations

import time

import pytest

from cryptozavr.infrastructure.providers.decorators.rate_limit import (
    RateLimitDecorator,
)
from cryptozavr.infrastructure.providers.rate_limiters import (
    RateLimiterRegistry,
)


class _StubProvider:
    venue_id = "kucoin"

    def __init__(self) -> None:
        self.calls = 0

    async def fetch_ticker(self, symbol: str) -> str:
        self.calls += 1
        return f"ticker-{symbol}"


@pytest.fixture
def registry() -> RateLimiterRegistry:
    reg = RateLimiterRegistry()
    reg.register("kucoin", rate_per_sec=100.0, capacity=1)
    return reg


@pytest.mark.asyncio
async def test_acquires_token_before_call(
    registry: RateLimiterRegistry,
) -> None:
    provider = _StubProvider()
    decorator = RateLimitDecorator(provider, limiter=registry.get("kucoin"))
    result = await decorator.fetch_ticker("BTC/USDT")
    assert result == "ticker-BTC/USDT"
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_blocks_when_rate_exceeded(
    registry: RateLimiterRegistry,
) -> None:
    provider = _StubProvider()
    decorator = RateLimitDecorator(provider, limiter=registry.get("kucoin"))
    await decorator.fetch_ticker("BTC/USDT")
    start = time.monotonic()
    await decorator.fetch_ticker("BTC/USDT")
    elapsed = time.monotonic() - start
    assert elapsed >= 0.005
    assert provider.calls == 2


@pytest.mark.asyncio
async def test_provider_exception_does_not_consume_extra_tokens(
    registry: RateLimiterRegistry,
) -> None:
    class _FailingProvider:
        venue_id = "kucoin"
        calls = 0

        async def fetch_ticker(self, symbol: str) -> str:
            self.calls += 1
            raise ValueError("boom")

    provider = _FailingProvider()
    decorator = RateLimitDecorator(provider, limiter=registry.get("kucoin"))
    with pytest.raises(ValueError, match="boom"):
        await decorator.fetch_ticker("BTC/USDT")
    assert provider.calls == 1
