"""RetryDecorator: exponential backoff + jitter for ProviderUnavailableError."""

from __future__ import annotations

import asyncio
import random
from typing import Any

from cryptozavr.domain.exceptions import ProviderUnavailableError
from cryptozavr.domain.interfaces import MarketDataProvider


class RetryDecorator:
    """Wraps a MarketDataProvider, retrying transient failures."""

    def __init__(
        self,
        inner: MarketDataProvider,
        *,
        max_attempts: int = 3,
        base_delay: float = 0.5,
        jitter: float = 0.2,
    ) -> None:
        self._inner = inner
        self._max_attempts = max_attempts
        self._base_delay = base_delay
        self._jitter = jitter
        self.venue_id = inner.venue_id

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def load_markets(self) -> None:
        await self._retry(self._inner.load_markets)

    async def fetch_ticker(self, symbol: Any) -> Any:
        return await self._retry(self._inner.fetch_ticker, symbol)

    async def fetch_ohlcv(self, *args: Any, **kwargs: Any) -> Any:
        return await self._retry(self._inner.fetch_ohlcv, *args, **kwargs)

    async def fetch_order_book(self, *args: Any, **kwargs: Any) -> Any:
        return await self._retry(self._inner.fetch_order_book, *args, **kwargs)

    async def fetch_trades(self, *args: Any, **kwargs: Any) -> Any:
        return await self._retry(self._inner.fetch_trades, *args, **kwargs)

    async def close(self) -> None:
        await self._inner.close()

    async def _retry(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        last_exc: Exception | None = None
        for attempt in range(self._max_attempts):
            try:
                return await fn(*args, **kwargs)
            except ProviderUnavailableError as exc:
                last_exc = exc
                if attempt == self._max_attempts - 1:
                    raise
                delay = self._base_delay * (2**attempt) + random.uniform(0, self._jitter)
                await asyncio.sleep(delay)
        assert last_exc is not None
        raise last_exc
