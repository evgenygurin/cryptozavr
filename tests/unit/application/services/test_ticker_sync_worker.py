"""TickerSyncWorker: force-refresh subscribed tickers periodically."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from cryptozavr.application.services.ticker_service import TickerService
from cryptozavr.application.services.ticker_sync_worker import TickerSyncWorker
from cryptozavr.infrastructure.supabase.realtime import (
    RealtimeSubscriber,
    TickerSubscription,
)


def _make_subscriber(subs: list[TickerSubscription]) -> RealtimeSubscriber:
    mock = MagicMock(spec=RealtimeSubscriber)
    mock.subscriptions.return_value = list(subs)
    return mock


@pytest.mark.asyncio
async def test_sync_once_with_no_subscriptions_is_noop() -> None:
    ticker_service = MagicMock(spec=TickerService)
    ticker_service.fetch_ticker = AsyncMock()
    worker = TickerSyncWorker(
        ticker_service=ticker_service,
        subscriber=_make_subscriber([]),
    )

    await worker.sync_once()

    ticker_service.fetch_ticker.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_once_force_refreshes_every_subscription() -> None:
    ticker_service = MagicMock(spec=TickerService)
    ticker_service.fetch_ticker = AsyncMock()
    subs = [
        TickerSubscription(venue_id="kucoin", symbol="BTC/USDT", channel_id="ch1"),
        TickerSubscription(venue_id="coingecko", symbol="ETH", channel_id="ch2"),
    ]
    worker = TickerSyncWorker(
        ticker_service=ticker_service,
        subscriber=_make_subscriber(subs),
    )

    await worker.sync_once()

    assert ticker_service.fetch_ticker.await_count == 2
    for call, sub in zip(ticker_service.fetch_ticker.await_args_list, subs, strict=True):
        assert call.kwargs == {
            "venue": sub.venue_id,
            "symbol": sub.symbol,
            "force_refresh": True,
        }


@pytest.mark.asyncio
async def test_sync_once_swallows_errors_per_subscription() -> None:
    ticker_service = MagicMock(spec=TickerService)
    ticker_service.fetch_ticker = AsyncMock(side_effect=[RuntimeError("boom"), None])
    subs = [
        TickerSubscription(venue_id="kucoin", symbol="BTC/USDT", channel_id="ch1"),
        TickerSubscription(venue_id="coingecko", symbol="ETH", channel_id="ch2"),
    ]
    worker = TickerSyncWorker(
        ticker_service=ticker_service,
        subscriber=_make_subscriber(subs),
    )

    await worker.sync_once()

    # Both subscriptions were attempted — error did not crash the loop.
    assert ticker_service.fetch_ticker.await_count == 2


@pytest.mark.asyncio
async def test_start_and_stop_runs_at_least_one_iteration() -> None:
    ticker_service = MagicMock(spec=TickerService)
    ticker_service.fetch_ticker = AsyncMock()
    worker = TickerSyncWorker(
        ticker_service=ticker_service,
        subscriber=_make_subscriber(
            [
                TickerSubscription(
                    venue_id="kucoin",
                    symbol="BTC/USDT",
                    channel_id="ch1",
                )
            ]
        ),
        interval_seconds=10.0,
    )

    await worker.start()
    for _ in range(10):
        await asyncio.sleep(0)
        if ticker_service.fetch_ticker.await_count >= 1:
            break
    await worker.stop()

    assert ticker_service.fetch_ticker.await_count >= 1
    assert not worker.is_running


@pytest.mark.asyncio
async def test_stop_is_idempotent() -> None:
    ticker_service = MagicMock(spec=TickerService)
    ticker_service.fetch_ticker = AsyncMock()
    worker = TickerSyncWorker(
        ticker_service=ticker_service,
        subscriber=_make_subscriber([]),
    )
    await worker.stop()
    await worker.start()
    await worker.stop()
    await worker.stop()
    assert not worker.is_running
