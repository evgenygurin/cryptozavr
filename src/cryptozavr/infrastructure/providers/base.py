"""BaseProvider: Template Method for provider fetch operations.

Subclasses override the abstract hooks; the skeleton stays fixed:
  1. state.require_operational()
  2. _ensure_markets_loaded()
  3. _fetch_*_raw()
  4. _normalize_*()
  5. catch → _translate_exception()
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from cryptozavr.domain.interfaces import MarketDataProvider
from cryptozavr.domain.market_data import (
    OHLCVSeries,
    OrderBookSnapshot,
    Ticker,
    TradeTick,
)
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Instant, Timeframe
from cryptozavr.domain.venues import VenueId
from cryptozavr.infrastructure.providers.state.venue_state import VenueState


class BaseProvider(ABC, MarketDataProvider):
    """Template Method skeleton for Domain MarketDataProvider implementations."""

    def __init__(self, *, venue_id: VenueId, state: VenueState) -> None:
        self.venue_id = venue_id
        self._state = state

    # ---- Public MarketDataProvider interface ----

    async def load_markets(self) -> None:
        await self._ensure_markets_loaded()

    async def fetch_ticker(self, symbol: Symbol) -> Ticker:
        return await self._execute_ticker(symbol)

    async def fetch_ohlcv(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        since: Instant | None = None,
        limit: int = 500,
    ) -> OHLCVSeries:
        return await self._execute_ohlcv(symbol, timeframe, since, limit)

    async def fetch_order_book(
        self,
        symbol: Symbol,
        depth: int = 50,
    ) -> OrderBookSnapshot:
        return await self._execute_orderbook(symbol, depth)

    async def fetch_trades(
        self,
        symbol: Symbol,
        since: Instant | None = None,
        limit: int = 100,
    ) -> tuple[TradeTick, ...]:
        return await self._execute_trades(symbol, since, limit)

    async def close(self) -> None:
        """Default no-op. Override if the underlying client needs closing."""
        return None

    # ---- Template Method ----

    async def _execute_ticker(self, symbol: Symbol) -> Ticker:
        self._state.require_operational()
        try:
            await self._ensure_markets_loaded()
            raw = await self._fetch_ticker_raw(symbol)
        except Exception as exc:
            raise self._translate_exception(exc) from exc
        return self._normalize_ticker(raw, symbol)

    async def _execute_ohlcv(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        since: Instant | None,
        limit: int,
    ) -> OHLCVSeries:
        self._state.require_operational()
        try:
            await self._ensure_markets_loaded()
            raw = await self._fetch_ohlcv_raw(symbol, timeframe, since, limit)
        except Exception as exc:
            raise self._translate_exception(exc) from exc
        return self._normalize_ohlcv(raw, symbol, timeframe)

    async def _execute_orderbook(
        self,
        symbol: Symbol,
        depth: int,
    ) -> OrderBookSnapshot:
        self._state.require_operational()
        try:
            await self._ensure_markets_loaded()
            raw = await self._fetch_order_book_raw(symbol, depth)
        except Exception as exc:
            raise self._translate_exception(exc) from exc
        return self._normalize_order_book(raw, symbol)

    async def _execute_trades(
        self,
        symbol: Symbol,
        since: Instant | None,
        limit: int,
    ) -> tuple[TradeTick, ...]:
        self._state.require_operational()
        try:
            await self._ensure_markets_loaded()
            raw = await self._fetch_trades_raw(symbol, since, limit)
        except Exception as exc:
            raise self._translate_exception(exc) from exc
        return self._normalize_trades(raw, symbol)

    # ---- Abstract hooks ----

    @abstractmethod
    async def _ensure_markets_loaded(self) -> None: ...

    @abstractmethod
    async def _fetch_ticker_raw(self, symbol: Symbol) -> Any: ...

    @abstractmethod
    def _normalize_ticker(self, raw: Any, symbol: Symbol) -> Ticker: ...

    async def _fetch_ohlcv_raw(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        since: Instant | None,
        limit: int,
    ) -> Any:
        raise NotImplementedError("ohlcv not implemented for this provider")

    def _normalize_ohlcv(
        self,
        raw: Any,
        symbol: Symbol,
        timeframe: Timeframe,
    ) -> OHLCVSeries:
        raise NotImplementedError("ohlcv not implemented for this provider")

    async def _fetch_order_book_raw(self, symbol: Symbol, depth: int) -> Any:
        raise NotImplementedError("order_book not implemented for this provider")

    def _normalize_order_book(
        self,
        raw: Any,
        symbol: Symbol,
    ) -> OrderBookSnapshot:
        raise NotImplementedError("order_book not implemented for this provider")

    async def _fetch_trades_raw(
        self,
        symbol: Symbol,
        since: Instant | None,
        limit: int,
    ) -> Any:
        raise NotImplementedError("trades not implemented for this provider")

    def _normalize_trades(
        self,
        raw: Any,
        symbol: Symbol,
    ) -> tuple[TradeTick, ...]:
        raise NotImplementedError("trades not implemented for this provider")

    @abstractmethod
    def _translate_exception(self, exc: Exception) -> Exception: ...
