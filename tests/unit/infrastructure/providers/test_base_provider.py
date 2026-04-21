"""Test BaseProvider Template Method via fake subclass."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pytest

from cryptozavr.domain.exceptions import (
    ProviderUnavailableError,
    RateLimitExceededError,
)
from cryptozavr.domain.market_data import Ticker
from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant
from cryptozavr.domain.venues import MarketType, VenueId, VenueStateKind
from cryptozavr.infrastructure.providers.base import BaseProvider
from cryptozavr.infrastructure.providers.state.venue_state import VenueState


@dataclass
class _FakeRawTicker:
    raw_last: str = "1.0"


class _FakeProvider(BaseProvider):
    """Minimal concrete subclass for pipeline testing."""

    def __init__(
        self,
        venue_id: VenueId,
        state: VenueState,
        *,
        ensure_markets_raises: Exception | None = None,
        fetch_ticker_raises: Exception | None = None,
    ) -> None:
        super().__init__(venue_id=venue_id, state=state)
        self.ensure_markets_called = 0
        self.fetch_ticker_called = 0
        self._ensure_markets_raises = ensure_markets_raises
        self._fetch_ticker_raises = fetch_ticker_raises

    async def _ensure_markets_loaded(self) -> None:
        self.ensure_markets_called += 1
        if self._ensure_markets_raises:
            raise self._ensure_markets_raises

    async def _fetch_ticker_raw(self, symbol: object) -> _FakeRawTicker:
        self.fetch_ticker_called += 1
        if self._fetch_ticker_raises:
            raise self._fetch_ticker_raises
        return _FakeRawTicker()

    def _normalize_ticker(self, raw: _FakeRawTicker, symbol: object) -> Ticker:
        return Ticker(
            symbol=symbol,  # type: ignore[arg-type]
            last=Decimal(raw.raw_last),
            observed_at=Instant.now(),
            quality=DataQuality(
                source=Provenance(
                    venue_id=self.venue_id.value,
                    endpoint="fetch_ticker",
                ),
                fetched_at=Instant.now(),
                staleness=Staleness.FRESH,
                confidence=Confidence.HIGH,
                cache_hit=False,
            ),
        )

    def _translate_exception(self, exc: Exception) -> Exception:
        return exc


@pytest.fixture
def registry() -> SymbolRegistry:
    return SymbolRegistry()


@pytest.fixture
def btc_symbol(registry: SymbolRegistry) -> Any:
    return registry.get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )


@pytest.mark.asyncio
async def test_fetch_ticker_happy_path(btc_symbol: Any) -> None:
    state = VenueState(VenueId.KUCOIN)
    provider = _FakeProvider(VenueId.KUCOIN, state)
    ticker = await provider.fetch_ticker(btc_symbol)
    assert ticker.last == Decimal("1.0")
    assert provider.ensure_markets_called == 1
    assert provider.fetch_ticker_called == 1


@pytest.mark.asyncio
async def test_fetch_ticker_rejects_when_venue_down(btc_symbol: Any) -> None:
    state = VenueState(VenueId.KUCOIN, kind=VenueStateKind.DOWN)
    provider = _FakeProvider(VenueId.KUCOIN, state)
    with pytest.raises(ProviderUnavailableError):
        await provider.fetch_ticker(btc_symbol)
    assert provider.ensure_markets_called == 0


@pytest.mark.asyncio
async def test_fetch_ticker_calls_ensure_markets_every_time(btc_symbol: Any) -> None:
    state = VenueState(VenueId.KUCOIN)
    provider = _FakeProvider(VenueId.KUCOIN, state)
    await provider.fetch_ticker(btc_symbol)
    await provider.fetch_ticker(btc_symbol)
    # BaseProvider invokes the hook each time; subclass decides caching.
    assert provider.ensure_markets_called == 2


@pytest.mark.asyncio
async def test_fetch_ticker_translates_raw_exception(btc_symbol: Any) -> None:
    state = VenueState(VenueId.KUCOIN)

    class _CustomProvider(_FakeProvider):
        def _translate_exception(self, exc: Exception) -> Exception:
            if isinstance(exc, ValueError):
                return RateLimitExceededError("rate limit hit")
            return exc

    raw_exc = ValueError("429 too many requests")
    provider = _CustomProvider(
        VenueId.KUCOIN,
        state,
        fetch_ticker_raises=raw_exc,
    )
    with pytest.raises(RateLimitExceededError, match="rate limit hit"):
        await provider.fetch_ticker(btc_symbol)
