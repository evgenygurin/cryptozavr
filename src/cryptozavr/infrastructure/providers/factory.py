"""ProviderFactory: Factory Method producing fully-decorated providers."""

from __future__ import annotations

from typing import Any

from cryptozavr.domain.venues import VenueId
from cryptozavr.infrastructure.providers.ccxt_provider import CCXTProvider
from cryptozavr.infrastructure.providers.coingecko_provider import (
    CoinGeckoProvider,
)
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
from cryptozavr.infrastructure.providers.http import HttpClientRegistry
from cryptozavr.infrastructure.providers.rate_limiters import RateLimiterRegistry
from cryptozavr.infrastructure.providers.state.venue_state import VenueState

_COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"


class ProviderFactory:
    """Factory Method for fully-wired providers.

    Each create_* method returns a LoggingDecorator-wrapped chain:
    Logging > Caching > RateLimit > Retry > base provider.
    """

    def __init__(
        self,
        *,
        http_registry: HttpClientRegistry,
        rate_registry: RateLimiterRegistry,
        retry_max_attempts: int = 3,
        retry_base_delay: float = 0.5,
        retry_jitter: float = 0.2,
        ticker_ttl: float = 5.0,
        ohlcv_ttl: float = 60.0,
        order_book_ttl: float = 3.0,
    ) -> None:
        self._http = http_registry
        self._rate = rate_registry
        self._retry_max_attempts = retry_max_attempts
        self._retry_base_delay = retry_base_delay
        self._retry_jitter = retry_jitter
        self._ticker_ttl = ticker_ttl
        self._ohlcv_ttl = ohlcv_ttl
        self._order_book_ttl = order_book_ttl

    def create_kucoin(
        self,
        *,
        state: VenueState,
        exchange: Any | None = None,
        **ccxt_opts: Any,
    ) -> LoggingDecorator:
        """Build KuCoin provider with full decorator chain.

        Pass `exchange` (fake) for tests; omit for real ccxt.kucoin().
        """
        if exchange is None:
            base = CCXTProvider.for_kucoin(state=state, **ccxt_opts)
        else:
            base = CCXTProvider(
                venue_id=VenueId.KUCOIN,
                state=state,
                exchange=exchange,
            )
        return self._wrap(base, venue_id="kucoin")

    async def create_coingecko(
        self,
        *,
        state: VenueState,
    ) -> LoggingDecorator:
        """Build CoinGecko provider with full decorator chain."""
        client = await self._http.get(
            "coingecko",
            base_url=_COINGECKO_BASE_URL,
        )
        base = CoinGeckoProvider(state=state, client=client)
        return self._wrap(base, venue_id="coingecko")

    def _wrap(self, base: Any, *, venue_id: str) -> LoggingDecorator:
        limiter = self._rate.get(venue_id)
        wrapped: Any = RetryDecorator(
            base,
            max_attempts=self._retry_max_attempts,
            base_delay=self._retry_base_delay,
            jitter=self._retry_jitter,
        )
        wrapped = RateLimitDecorator(wrapped, limiter=limiter)
        wrapped = InMemoryCachingDecorator(
            wrapped,
            ticker_ttl=self._ticker_ttl,
            ohlcv_ttl=self._ohlcv_ttl,
            order_book_ttl=self._order_book_ttl,
        )
        return LoggingDecorator(wrapped)
