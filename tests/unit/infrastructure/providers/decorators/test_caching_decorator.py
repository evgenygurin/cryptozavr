"""Test InMemoryCachingDecorator: TTL cache, freezegun-controlled."""

from __future__ import annotations

import pytest
from freezegun import freeze_time

from cryptozavr.infrastructure.providers.decorators.caching import (
    InMemoryCachingDecorator,
)


class _StubProvider:
    venue_id = "kucoin"

    def __init__(self) -> None:
        self.ticker_calls = 0

    async def fetch_ticker(self, symbol: str) -> str:
        self.ticker_calls += 1
        return f"ticker-{symbol}-v{self.ticker_calls}"


@pytest.mark.asyncio
async def test_first_call_is_cache_miss() -> None:
    provider = _StubProvider()
    decorator = InMemoryCachingDecorator(provider, ticker_ttl=10.0)
    result = await decorator.fetch_ticker("BTC/USDT")
    assert result == "ticker-BTC/USDT-v1"
    assert provider.ticker_calls == 1


@pytest.mark.asyncio
async def test_second_call_within_ttl_returns_cache() -> None:
    provider = _StubProvider()
    decorator = InMemoryCachingDecorator(provider, ticker_ttl=10.0)
    with freeze_time("2026-04-21 10:00:00") as frozen:
        r1 = await decorator.fetch_ticker("BTC/USDT")
        frozen.tick(5)
        r2 = await decorator.fetch_ticker("BTC/USDT")
    assert r1 == r2
    assert provider.ticker_calls == 1


@pytest.mark.asyncio
async def test_call_after_ttl_refetches() -> None:
    provider = _StubProvider()
    decorator = InMemoryCachingDecorator(provider, ticker_ttl=10.0)
    with freeze_time("2026-04-21 10:00:00") as frozen:
        await decorator.fetch_ticker("BTC/USDT")
        frozen.tick(11)
        r2 = await decorator.fetch_ticker("BTC/USDT")
    assert r2 == "ticker-BTC/USDT-v2"
    assert provider.ticker_calls == 2


@pytest.mark.asyncio
async def test_different_symbols_are_independent() -> None:
    provider = _StubProvider()
    decorator = InMemoryCachingDecorator(provider, ticker_ttl=10.0)
    await decorator.fetch_ticker("BTC/USDT")
    await decorator.fetch_ticker("ETH/USDT")
    assert provider.ticker_calls == 2


class _FakeProvider:
    """Exercises both ticker and ohlcv cache buckets for invalidation tests."""

    venue_id = "kucoin"

    def __init__(self) -> None:
        self.ticker_calls = 0
        self.ohlcv_calls = 0

    async def fetch_ticker(self, symbol: str) -> str:
        self.ticker_calls += 1
        return f"ticker-{symbol}-{self.ticker_calls}"

    async def fetch_ohlcv(self, symbol: str) -> str:
        self.ohlcv_calls += 1
        return f"ohlcv-{symbol}-{self.ohlcv_calls}"


@pytest.mark.asyncio
async def test_invalidate_tickers_drops_only_ticker_entries() -> None:
    base = _FakeProvider()
    cache = InMemoryCachingDecorator(base, ticker_ttl=60.0, ohlcv_ttl=60.0)

    first_ticker = await cache.fetch_ticker("BTC/USDT")
    first_ohlcv = await cache.fetch_ohlcv("BTC/USDT")

    cache.invalidate_tickers()

    second_ticker = await cache.fetch_ticker("BTC/USDT")
    second_ohlcv = await cache.fetch_ohlcv("BTC/USDT")

    assert first_ticker != second_ticker
    assert first_ohlcv == second_ohlcv
    assert base.ticker_calls == 2
    assert base.ohlcv_calls == 1


@pytest.mark.asyncio
async def test_invalidate_tickers_is_noop_when_cache_empty() -> None:
    base = _FakeProvider()
    cache = InMemoryCachingDecorator(base, ticker_ttl=60.0)
    cache.invalidate_tickers()
    result = await cache.fetch_ticker("BTC/USDT")
    assert result == "ticker-BTC/USDT-1"
