"""Test TokenBucket + RateLimiterRegistry."""

from __future__ import annotations

import time

import pytest

from cryptozavr.infrastructure.providers.rate_limiters import (
    RateLimiterRegistry,
    TokenBucket,
)


class TestTokenBucket:
    @pytest.mark.asyncio
    async def test_initial_capacity_allows_immediate_acquire(self) -> None:
        bucket = TokenBucket(rate_per_sec=10.0, capacity=5)
        start = time.monotonic()
        for _ in range(5):
            await bucket.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_exhausted_bucket_waits_for_refill(self) -> None:
        bucket = TokenBucket(rate_per_sec=10.0, capacity=2)
        await bucket.acquire()
        await bucket.acquire()
        start = time.monotonic()
        await bucket.acquire()
        elapsed = time.monotonic() - start
        assert 0.05 <= elapsed <= 0.25, f"expected ~100ms, got {elapsed * 1000:.0f}ms"

    @pytest.mark.asyncio
    async def test_rate_per_sec_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="rate_per_sec"):
            TokenBucket(rate_per_sec=0.0, capacity=1)

    @pytest.mark.asyncio
    async def test_capacity_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="capacity"):
            TokenBucket(rate_per_sec=1.0, capacity=0)


class TestRateLimiterRegistry:
    def test_get_returns_same_bucket_for_same_venue(self) -> None:
        registry = RateLimiterRegistry()
        registry.register("kucoin", rate_per_sec=30.0, capacity=30)
        a = registry.get("kucoin")
        b = registry.get("kucoin")
        assert a is b

    def test_get_unregistered_venue_raises(self) -> None:
        registry = RateLimiterRegistry()
        with pytest.raises(KeyError, match="kucoin"):
            registry.get("kucoin")

    def test_register_twice_for_same_venue_raises(self) -> None:
        registry = RateLimiterRegistry()
        registry.register("kucoin", rate_per_sec=30.0, capacity=30)
        with pytest.raises(ValueError, match="already registered"):
            registry.register("kucoin", rate_per_sec=10.0, capacity=10)

    def test_different_venues_get_different_buckets(self) -> None:
        registry = RateLimiterRegistry()
        registry.register("kucoin", rate_per_sec=30.0, capacity=30)
        registry.register("coingecko", rate_per_sec=0.5, capacity=30)
        assert registry.get("kucoin") is not registry.get("coingecko")
