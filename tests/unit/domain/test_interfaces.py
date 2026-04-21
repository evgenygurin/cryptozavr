"""Test Protocol structural subtyping for domain interfaces."""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.domain.interfaces import (
    Clock,
    MarketDataProvider,
    Repository,
)
from cryptozavr.domain.market_data import (
    OHLCVSeries,
    OrderBookSnapshot,
    Ticker,
    TradeTick,
)
from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Instant, Timeframe
from cryptozavr.domain.venues import VenueId


class _FakeProvider:
    """Minimal concrete impl for structural subtyping check."""

    venue_id = VenueId.KUCOIN

    async def load_markets(self) -> None:  # pragma: no cover
        pass

    async def fetch_ticker(self, symbol: Symbol) -> Ticker:
        return Ticker(
            symbol=symbol,
            last=Decimal("1"),
            observed_at=Instant.now(),
            quality=DataQuality(
                source=Provenance(venue_id="kucoin", endpoint="fetch_ticker"),
                fetched_at=Instant.now(),
                staleness=Staleness.FRESH,
                confidence=Confidence.HIGH,
                cache_hit=False,
            ),
        )

    async def fetch_ohlcv(  # pragma: no cover
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        since: Instant | None = None,
        limit: int = 500,
    ) -> OHLCVSeries:
        raise NotImplementedError

    async def fetch_order_book(  # pragma: no cover
        self,
        symbol: Symbol,
        depth: int = 50,
    ) -> OrderBookSnapshot:
        raise NotImplementedError

    async def fetch_trades(  # pragma: no cover
        self,
        symbol: Symbol,
        since: Instant | None = None,
        limit: int = 100,
    ) -> tuple[TradeTick, ...]:
        return ()

    async def close(self) -> None:  # pragma: no cover
        pass


class _FakeRepo:
    async def get(self, key: object) -> object | None:
        return None

    async def put(self, entity: object) -> None:
        pass

    async def list(self, **filters: object) -> list[object]:
        return []


class _FakeClock:
    def now(self) -> Instant:
        return Instant.now()


def test_FakeProvider_conforms_to_MarketDataProvider() -> None:
    provider: MarketDataProvider = _FakeProvider()
    assert provider.venue_id == VenueId.KUCOIN


def test_FakeRepo_conforms_to_Repository() -> None:
    repo: Repository[object] = _FakeRepo()
    assert repo is not None


def test_FakeClock_conforms_to_Clock() -> None:
    clock: Clock = _FakeClock()
    assert isinstance(clock.now(), Instant)
