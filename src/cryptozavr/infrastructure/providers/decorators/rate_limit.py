"""RateLimitDecorator: acquires a token before each provider call."""

from __future__ import annotations

from typing import Any

from cryptozavr.domain.interfaces import MarketDataProvider
from cryptozavr.infrastructure.providers.rate_limiters import TokenBucket


class RateLimitDecorator:
    """Wraps a MarketDataProvider, throttling calls via a TokenBucket."""

    def __init__(
        self,
        inner: MarketDataProvider,
        *,
        limiter: TokenBucket,
    ) -> None:
        self._inner = inner
        self._limiter = limiter
        self.venue_id = inner.venue_id

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def load_markets(self) -> None:
        await self._limiter.acquire()
        await self._inner.load_markets()

    async def fetch_ticker(self, symbol: Any) -> Any:
        await self._limiter.acquire()
        return await self._inner.fetch_ticker(symbol)

    async def fetch_ohlcv(self, *args: Any, **kwargs: Any) -> Any:
        await self._limiter.acquire()
        return await self._inner.fetch_ohlcv(*args, **kwargs)

    async def fetch_order_book(self, *args: Any, **kwargs: Any) -> Any:
        await self._limiter.acquire()
        return await self._inner.fetch_order_book(*args, **kwargs)

    async def fetch_trades(self, *args: Any, **kwargs: Any) -> Any:
        await self._limiter.acquire()
        return await self._inner.fetch_trades(*args, **kwargs)

    async def close(self) -> None:
        await self._inner.close()
