"""MetricsDecorator: emits Prometheus-compatible counter+histogram per provider call."""

from __future__ import annotations

import time
from typing import Any

from cryptozavr.domain.exceptions import RateLimitExceededError
from cryptozavr.domain.interfaces import MarketDataProvider
from cryptozavr.infrastructure.observability.metrics import MetricsRegistry


class MetricsDecorator:
    """Wraps a MarketDataProvider and records provider_calls_total + duration."""

    def __init__(
        self,
        inner: MarketDataProvider,
        *,
        registry: MetricsRegistry,
    ) -> None:
        self._inner = inner
        self._registry = registry
        self.venue_id = inner.venue_id

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def load_markets(self) -> None:
        await self._measure("load_markets", self._inner.load_markets)

    async def fetch_ticker(self, symbol: Any) -> Any:
        return await self._measure(
            "fetch_ticker",
            self._inner.fetch_ticker,
            symbol,
        )

    async def fetch_ohlcv(self, *args: Any, **kwargs: Any) -> Any:
        return await self._measure(
            "fetch_ohlcv",
            self._inner.fetch_ohlcv,
            *args,
            **kwargs,
        )

    async def fetch_order_book(self, *args: Any, **kwargs: Any) -> Any:
        return await self._measure(
            "fetch_order_book",
            self._inner.fetch_order_book,
            *args,
            **kwargs,
        )

    async def fetch_trades(self, *args: Any, **kwargs: Any) -> Any:
        return await self._measure(
            "fetch_trades",
            self._inner.fetch_trades,
            *args,
            **kwargs,
        )

    async def close(self) -> None:
        await self._inner.close()

    async def _measure(
        self,
        endpoint: str,
        fn: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        start = time.monotonic()
        outcome = "ok"
        try:
            return await fn(*args, **kwargs)
        except RateLimitExceededError:
            outcome = "rate_limited"
            raise
        except TimeoutError:
            outcome = "timeout"
            raise
        except Exception:
            outcome = "error"
            raise
        finally:
            duration_ms = (time.monotonic() - start) * 1000.0
            base_labels = {
                "venue": str(self.venue_id),
                "endpoint": endpoint,
            }
            self._registry.inc_counter(
                "provider_calls_total",
                labels={**base_labels, "outcome": outcome},
            )
            self._registry.observe_histogram(
                "provider_call_duration_ms",
                labels=base_labels,
                value=duration_ms,
            )
