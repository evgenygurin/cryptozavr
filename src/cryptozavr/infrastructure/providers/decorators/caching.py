"""InMemoryCachingDecorator: L0 TTL cache for ticker/ohlcv/orderbook."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from cryptozavr.domain.interfaces import MarketDataProvider


@dataclass
class _Entry:
    value: Any
    expires_at: float


class InMemoryCachingDecorator:
    """Wraps a MarketDataProvider with TTL-based in-memory caching."""

    def __init__(
        self,
        inner: MarketDataProvider,
        *,
        ticker_ttl: float = 5.0,
        ohlcv_ttl: float = 60.0,
        order_book_ttl: float = 3.0,
    ) -> None:
        self._inner = inner
        self._ticker_ttl = ticker_ttl
        self._ohlcv_ttl = ohlcv_ttl
        self._order_book_ttl = order_book_ttl
        self._cache: dict[str, _Entry] = {}
        self.venue_id = inner.venue_id

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def load_markets(self) -> None:
        await self._inner.load_markets()

    async def fetch_ticker(self, symbol: Any) -> Any:
        key = f"ticker:{symbol!r}"
        return await self._cached(
            key,
            self._ticker_ttl,
            self._inner.fetch_ticker,
            symbol,
        )

    async def fetch_ohlcv(self, *args: Any, **kwargs: Any) -> Any:
        key = f"ohlcv:{args!r}:{sorted(kwargs.items())!r}"
        return await self._cached(
            key,
            self._ohlcv_ttl,
            self._inner.fetch_ohlcv,
            *args,
            **kwargs,
        )

    async def fetch_order_book(self, *args: Any, **kwargs: Any) -> Any:
        key = f"orderbook:{args!r}:{sorted(kwargs.items())!r}"
        return await self._cached(
            key,
            self._order_book_ttl,
            self._inner.fetch_order_book,
            *args,
            **kwargs,
        )

    async def fetch_trades(self, *args: Any, **kwargs: Any) -> Any:
        return await self._inner.fetch_trades(*args, **kwargs)

    async def close(self) -> None:
        await self._inner.close()

    async def _cached(
        self,
        key: str,
        ttl: float,
        fn: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        now = time.time()
        entry = self._cache.get(key)
        if entry is not None and entry.expires_at > now:
            return entry.value
        value = await fn(*args, **kwargs)
        self._cache[key] = _Entry(value=value, expires_at=now + ttl)
        return value
