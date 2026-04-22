"""CacheInvalidator: realtime payload dispatch + provider.invalidate_tickers."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from cryptozavr.application.services.cache_invalidator import CacheInvalidator
from cryptozavr.domain.venues import VenueId
from cryptozavr.infrastructure.supabase.realtime import (
    RealtimeSubscriber,
    SubscriptionHandle,
)


class _FakeCacheProvider:
    """Minimal stand-in for a LoggingDecorator-wrapped chain."""

    def __init__(self) -> None:
        self.invalidations = 0

    def invalidate_tickers(self) -> None:
        self.invalidations += 1


def _make_subscriber() -> RealtimeSubscriber:
    mock = MagicMock(spec=RealtimeSubscriber)
    mock.subscribe_tickers = AsyncMock(
        side_effect=lambda venue_id, callback: SubscriptionHandle(channel_id=f"ch-{venue_id}")
    )
    return mock


def test_on_ticker_change_dispatches_to_matching_provider() -> None:
    kucoin_provider = _FakeCacheProvider()
    coingecko_provider = _FakeCacheProvider()
    invalidator = CacheInvalidator(
        subscriber=_make_subscriber(),
        providers={
            VenueId.KUCOIN: kucoin_provider,
            VenueId.COINGECKO: coingecko_provider,
        },
    )

    invalidator.on_ticker_change({"record": {"venue_id": "kucoin"}})

    assert kucoin_provider.invalidations == 1
    assert coingecko_provider.invalidations == 0


def test_on_ticker_change_ignores_unknown_venue() -> None:
    provider = _FakeCacheProvider()
    invalidator = CacheInvalidator(
        subscriber=_make_subscriber(),
        providers={VenueId.KUCOIN: provider},
    )

    invalidator.on_ticker_change({"record": {"venue_id": "binance"}})

    assert provider.invalidations == 0


def test_on_ticker_change_pessimistic_when_venue_missing() -> None:
    """tickers_live has no venue_id column, so a callback may see a payload
    with only symbol_id. The invalidator must then drop ticker caches on
    every known venue rather than silently do nothing (reviewer finding)."""
    kucoin = _FakeCacheProvider()
    coingecko = _FakeCacheProvider()
    invalidator = CacheInvalidator(
        subscriber=_make_subscriber(),
        providers={VenueId.KUCOIN: kucoin, VenueId.COINGECKO: coingecko},
    )

    invalidator.on_ticker_change({"record": {"symbol_id": 42}})

    assert kucoin.invalidations == 1
    assert coingecko.invalidations == 1


def test_on_ticker_change_extracts_venue_from_record_venue_alias() -> None:
    """`record.venue` is one of 4 fallback extraction paths."""
    provider = _FakeCacheProvider()
    invalidator = CacheInvalidator(
        subscriber=_make_subscriber(),
        providers={VenueId.KUCOIN: provider},
    )
    invalidator.on_ticker_change({"record": {"venue": "kucoin"}})
    assert provider.invalidations == 1


def test_on_ticker_change_extracts_venue_from_data_key() -> None:
    """`data.venue_id` is another fallback path (supabase-py variations)."""
    provider = _FakeCacheProvider()
    invalidator = CacheInvalidator(
        subscriber=_make_subscriber(),
        providers={VenueId.KUCOIN: provider},
    )
    invalidator.on_ticker_change({"data": {"venue_id": "kucoin"}})
    assert provider.invalidations == 1


def test_on_ticker_change_extracts_top_level_venue_id() -> None:
    """Top-level `venue_id` is the last fallback path."""
    provider = _FakeCacheProvider()
    invalidator = CacheInvalidator(
        subscriber=_make_subscriber(),
        providers={VenueId.KUCOIN: provider},
    )
    invalidator.on_ticker_change({"venue_id": "kucoin"})
    assert provider.invalidations == 1


def test_on_ticker_change_ignores_non_dict_payload() -> None:
    provider = _FakeCacheProvider()
    invalidator = CacheInvalidator(
        subscriber=_make_subscriber(),
        providers={VenueId.KUCOIN: provider},
    )

    invalidator.on_ticker_change("not a dict")
    invalidator.on_ticker_change(None)

    assert provider.invalidations == 0


def test_on_ticker_change_skips_provider_without_invalidate_tickers() -> None:
    class _NoInvalidate:
        pass

    invalidator = CacheInvalidator(
        subscriber=_make_subscriber(),
        providers={VenueId.KUCOIN: _NoInvalidate()},
    )

    # Should not raise.
    invalidator.on_ticker_change({"record": {"venue_id": "kucoin"}})


def test_on_ticker_change_swallows_invalidator_exceptions(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class _Boom:
        def invalidate_tickers(self) -> None:
            raise RuntimeError("boom")

    invalidator = CacheInvalidator(
        subscriber=_make_subscriber(),
        providers={VenueId.KUCOIN: _Boom()},
    )
    invalidator.on_ticker_change({"record": {"venue_id": "kucoin"}})
    assert any("cache invalidation failed" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_start_subscribes_to_each_venue() -> None:
    subscriber = _make_subscriber()
    invalidator = CacheInvalidator(
        subscriber=subscriber,
        providers={
            VenueId.KUCOIN: _FakeCacheProvider(),
            VenueId.COINGECKO: _FakeCacheProvider(),
        },
    )

    await invalidator.start()

    assert subscriber.subscribe_tickers.await_count == 2
    # Every call forwarded the invalidator.on_ticker_change bound method.
    for call in subscriber.subscribe_tickers.await_args_list:
        callback = call.kwargs["callback"]
        assert callback.__func__ is CacheInvalidator.on_ticker_change
        assert callback.__self__ is invalidator


@pytest.mark.asyncio
async def test_start_is_idempotent() -> None:
    subscriber = _make_subscriber()
    invalidator = CacheInvalidator(
        subscriber=subscriber,
        providers={VenueId.KUCOIN: _FakeCacheProvider()},
    )

    await invalidator.start()
    await invalidator.start()

    assert subscriber.subscribe_tickers.await_count == 1


@pytest.mark.asyncio
async def test_start_logs_and_continues_on_subscribe_failure() -> None:
    subscriber = MagicMock(spec=RealtimeSubscriber)

    async def flaky(venue_id: str, callback: Any) -> SubscriptionHandle:
        if venue_id == "kucoin":
            raise RuntimeError("no client")
        return SubscriptionHandle(channel_id=f"ch-{venue_id}")

    subscriber.subscribe_tickers = AsyncMock(side_effect=flaky)

    invalidator = CacheInvalidator(
        subscriber=subscriber,
        providers={
            VenueId.KUCOIN: _FakeCacheProvider(),
            VenueId.COINGECKO: _FakeCacheProvider(),
        },
    )

    await invalidator.start()

    assert subscriber.subscribe_tickers.await_count == 2
