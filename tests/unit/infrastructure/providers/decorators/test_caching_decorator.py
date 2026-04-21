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
