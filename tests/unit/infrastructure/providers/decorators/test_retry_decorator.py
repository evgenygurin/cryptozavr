"""Test RetryDecorator: exponential backoff on ProviderUnavailableError."""

from __future__ import annotations

import pytest

from cryptozavr.domain.exceptions import (
    ProviderUnavailableError,
    RateLimitExceededError,
)
from cryptozavr.infrastructure.providers.decorators.retry import RetryDecorator


class _StubProvider:
    venue_id = "test"

    def __init__(
        self,
        *,
        failures: int = 0,
        rate_limit_after: int = -1,
    ) -> None:
        self._failures = failures
        self._rate_limit_after = rate_limit_after
        self.calls = 0

    async def fetch_ticker(self, symbol: str) -> str:
        self.calls += 1
        if self.calls <= self._rate_limit_after:
            raise RateLimitExceededError("429")
        if self.calls <= self._failures:
            raise ProviderUnavailableError("timeout")
        return f"ticker-{symbol}"


@pytest.mark.asyncio
async def test_succeeds_on_first_attempt() -> None:
    provider = _StubProvider(failures=0)
    decorator = RetryDecorator(
        provider,
        max_attempts=3,
        base_delay=0.001,
        jitter=0.0,
    )
    result = await decorator.fetch_ticker("BTC/USDT")
    assert result == "ticker-BTC/USDT"
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_retries_on_provider_unavailable() -> None:
    provider = _StubProvider(failures=2)
    decorator = RetryDecorator(
        provider,
        max_attempts=3,
        base_delay=0.001,
        jitter=0.0,
    )
    result = await decorator.fetch_ticker("BTC/USDT")
    assert result == "ticker-BTC/USDT"
    assert provider.calls == 3


@pytest.mark.asyncio
async def test_raises_after_max_attempts() -> None:
    provider = _StubProvider(failures=5)
    decorator = RetryDecorator(
        provider,
        max_attempts=3,
        base_delay=0.001,
        jitter=0.0,
    )
    with pytest.raises(ProviderUnavailableError):
        await decorator.fetch_ticker("BTC/USDT")
    assert provider.calls == 3


@pytest.mark.asyncio
async def test_does_not_retry_on_rate_limit() -> None:
    provider = _StubProvider(rate_limit_after=5)
    decorator = RetryDecorator(
        provider,
        max_attempts=3,
        base_delay=0.001,
        jitter=0.0,
    )
    with pytest.raises(RateLimitExceededError):
        await decorator.fetch_ticker("BTC/USDT")
    assert provider.calls == 1
