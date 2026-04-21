"""LoggingDecorator: structured per-call logs via stdlib logging."""

from __future__ import annotations

import logging
import time
from typing import Any

from cryptozavr.domain.interfaces import MarketDataProvider


class LoggingDecorator:
    """Wraps a MarketDataProvider, logging each call duration + outcome."""

    def __init__(
        self,
        inner: MarketDataProvider,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._inner = inner
        self._logger = logger or logging.getLogger(f"cryptozavr.providers.{inner.venue_id}")
        self.venue_id = inner.venue_id

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def load_markets(self) -> None:
        await self._call("load_markets", self._inner.load_markets)

    async def fetch_ticker(self, symbol: Any) -> Any:
        return await self._call(
            "fetch_ticker",
            self._inner.fetch_ticker,
            symbol,
        )

    async def fetch_ohlcv(self, *args: Any, **kwargs: Any) -> Any:
        return await self._call(
            "fetch_ohlcv",
            self._inner.fetch_ohlcv,
            *args,
            **kwargs,
        )

    async def fetch_order_book(self, *args: Any, **kwargs: Any) -> Any:
        return await self._call(
            "fetch_order_book",
            self._inner.fetch_order_book,
            *args,
            **kwargs,
        )

    async def fetch_trades(self, *args: Any, **kwargs: Any) -> Any:
        return await self._call(
            "fetch_trades",
            self._inner.fetch_trades,
            *args,
            **kwargs,
        )

    async def close(self) -> None:
        await self._inner.close()

    async def _call(self, op: str, fn: Any, *args: Any, **kwargs: Any) -> Any:
        start = time.monotonic()
        self._logger.debug("%s called on %s", op, self.venue_id)
        try:
            result = await fn(*args, **kwargs)
        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            self._logger.warning(
                "%s on %s failed after %.1fms: %s",
                op,
                self.venue_id,
                duration_ms,
                exc,
            )
            raise
        duration_ms = (time.monotonic() - start) * 1000
        self._logger.info(
            "%s on %s succeeded in %.1fms",
            op,
            self.venue_id,
            duration_ms,
        )
        return result
