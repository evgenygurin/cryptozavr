"""Protocol interfaces for domain-level dependencies.

Concrete implementations live in L2 (Infrastructure). L3/L4 depend only on Protocols.
"""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from cryptozavr.domain.market_data import (
    OHLCVSeries,
    OrderBookSnapshot,
    Ticker,
    TradeTick,
)
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Instant, Timeframe
from cryptozavr.domain.venues import VenueId

T = TypeVar("T")


@runtime_checkable
class MarketDataProvider(Protocol):
    """Read-only market data provider.

    Implementations in infrastructure.providers translate vendor-specific APIs
    into these Domain methods. All methods are async.
    """

    venue_id: VenueId

    async def load_markets(self) -> None: ...

    async def fetch_ticker(self, symbol: Symbol) -> Ticker: ...

    async def fetch_ohlcv(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        since: Instant | None = None,
        limit: int = 500,
    ) -> OHLCVSeries: ...

    async def fetch_order_book(
        self,
        symbol: Symbol,
        depth: int = 50,
    ) -> OrderBookSnapshot: ...

    async def fetch_trades(
        self,
        symbol: Symbol,
        since: Instant | None = None,
        limit: int = 100,
    ) -> tuple[TradeTick, ...]: ...

    async def close(self) -> None: ...


@runtime_checkable
class Repository(Protocol[T]):
    """Generic aggregate-root repository. Concrete impls in infrastructure.repositories."""

    async def get(self, key: object) -> T | None: ...

    async def put(self, entity: T) -> None: ...

    async def list(self, **filters: object) -> list[T]: ...


@runtime_checkable
class Clock(Protocol):
    """Injectable time source for testability (FrozenClock in tests)."""

    def now(self) -> Instant: ...
