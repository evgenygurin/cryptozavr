"""CCXTProvider: concrete BaseProvider using ccxt.async_support."""

from __future__ import annotations

from typing import Any, Protocol

import ccxt.async_support as ccxt_async

from cryptozavr.domain.exceptions import (
    ProviderUnavailableError,
    RateLimitExceededError,
)
from cryptozavr.domain.market_data import (
    OHLCVSeries,
    OrderBookSnapshot,
    Ticker,
)
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Instant, Timeframe
from cryptozavr.domain.venues import VenueId
from cryptozavr.infrastructure.providers.adapters.ccxt_adapter import CCXTAdapter
from cryptozavr.infrastructure.providers.base import BaseProvider
from cryptozavr.infrastructure.providers.state.venue_state import VenueState


class _ExchangeProtocol(Protocol):
    """Duck-type matching ccxt.async_support.Exchange subset we use."""

    async def load_markets(self) -> Any: ...
    async def fetch_ticker(self, symbol: str) -> Any: ...
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: int | None = ...,
        limit: int = ...,
    ) -> Any: ...
    async def fetch_order_book(self, symbol: str, limit: int = ...) -> Any: ...
    async def close(self) -> Any: ...


class CCXTProvider(BaseProvider):
    """CCXT-powered provider. Works with any CCXT exchange (start with kucoin)."""

    def __init__(
        self,
        *,
        venue_id: VenueId,
        state: VenueState,
        exchange: _ExchangeProtocol,
    ) -> None:
        super().__init__(venue_id=venue_id, state=state)
        self._exchange = exchange
        self._markets_loaded = False

    @classmethod
    def for_kucoin(
        cls,
        *,
        state: VenueState,
        **ccxt_opts: Any,
    ) -> CCXTProvider:
        """Factory helper: build a CCXTProvider wrapping ccxt.kucoin()."""
        exchange = ccxt_async.kucoin({**ccxt_opts, "enableRateLimit": False})
        return cls(
            venue_id=VenueId.KUCOIN,
            state=state,
            exchange=exchange,
        )

    async def _ensure_markets_loaded(self) -> None:
        if not self._markets_loaded:
            await self._exchange.load_markets()
            self._markets_loaded = True

    async def _fetch_ticker_raw(self, symbol: Symbol) -> Any:
        return await self._exchange.fetch_ticker(symbol.native_symbol)

    def _normalize_ticker(self, raw: Any, symbol: Symbol) -> Ticker:
        return CCXTAdapter.ticker_to_domain(raw, symbol)

    async def _fetch_ohlcv_raw(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        since: Instant | None,
        limit: int,
    ) -> Any:
        return await self._exchange.fetch_ohlcv(
            symbol.native_symbol,
            timeframe.to_ccxt_string(),
            since=since.to_ms() if since else None,
            limit=limit,
        )

    def _normalize_ohlcv(
        self,
        raw: Any,
        symbol: Symbol,
        timeframe: Timeframe,
    ) -> OHLCVSeries:
        return CCXTAdapter.ohlcv_to_series(raw, symbol, timeframe)

    async def _fetch_order_book_raw(self, symbol: Symbol, depth: int) -> Any:
        return await self._exchange.fetch_order_book(
            symbol.native_symbol,
            limit=depth,
        )

    def _normalize_order_book(
        self,
        raw: Any,
        symbol: Symbol,
    ) -> OrderBookSnapshot:
        return CCXTAdapter.orderbook_to_domain(raw, symbol)

    def _translate_exception(self, exc: Exception) -> Exception:
        if isinstance(exc, ccxt_async.RateLimitExceeded):
            return RateLimitExceededError(str(exc))
        if isinstance(exc, ccxt_async.NetworkError):
            return ProviderUnavailableError(str(exc))
        return exc

    async def close(self) -> None:
        await self._exchange.close()
