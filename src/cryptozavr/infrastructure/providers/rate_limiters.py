"""Token bucket rate limiter + per-venue registry."""

from __future__ import annotations

import asyncio
import time


class TokenBucket:
    """Classic token bucket: `rate_per_sec` tokens added up to `capacity`.

    `acquire()` blocks until a token is available, then consumes one.
    """

    def __init__(self, *, rate_per_sec: float, capacity: int) -> None:
        if rate_per_sec <= 0:
            raise ValueError("rate_per_sec must be > 0")
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        self._rate = rate_per_sec
        self._capacity = capacity
        self._tokens: float = float(capacity)
        self._updated_at = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Block until one token is available, then consume it."""
        async with self._lock:
            while True:
                now = time.monotonic()
                delta = now - self._updated_at
                self._tokens = min(self._capacity, self._tokens + delta * self._rate)
                self._updated_at = now
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                deficit = 1 - self._tokens
                sleep_for = deficit / self._rate
                await asyncio.sleep(sleep_for)


class RateLimiterRegistry:
    """Per-venue TokenBucket registry. `register` once at startup, `get` at runtime."""

    def __init__(self) -> None:
        self._buckets: dict[str, TokenBucket] = {}

    def register(
        self,
        venue_id: str,
        *,
        rate_per_sec: float,
        capacity: int,
    ) -> None:
        """Register a bucket for venue_id."""
        if venue_id in self._buckets:
            raise ValueError(f"venue {venue_id!r} already registered")
        self._buckets[venue_id] = TokenBucket(
            rate_per_sec=rate_per_sec,
            capacity=capacity,
        )

    def get(self, venue_id: str) -> TokenBucket:
        """Return the bucket for venue_id or raise KeyError."""
        try:
            return self._buckets[venue_id]
        except KeyError as exc:
            raise KeyError(f"venue {venue_id!r} has no registered rate limiter") from exc
