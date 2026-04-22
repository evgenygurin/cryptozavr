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
        TickerSubscription(
            venue_id="kucoin",
            symbol="BTC/USDT",
            channel_id=TickerSubscription.make_channel_id("kucoin", "BTC/USDT"),
        ),
        TickerSubscription(
            venue_id="coingecko",
            symbol="ETH",
            channel_id=TickerSubscription.make_channel_id("coingecko", "ETH"),
        ),
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
        TickerSubscription(
            venue_id="kucoin",
            symbol="BTC/USDT",
            channel_id=TickerSubscription.make_channel_id("kucoin", "BTC/USDT"),
        ),
        TickerSubscription(
            venue_id="coingecko",
            symbol="ETH",
            channel_id=TickerSubscription.make_channel_id("coingecko", "ETH"),
        ),
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
                    channel_id=TickerSubscription.make_channel_id("kucoin", "BTC/USDT"),
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
async def test_sync_once_runs_subscriptions_concurrently() -> None:
    """Force-refresh must fan out via asyncio.gather, not serial per subscription."""
    max_concurrent = 0
    current = 0
    lock = asyncio.Lock()

    async def tracking_fetch(**_kwargs):
        nonlocal max_concurrent, current
        async with lock:
            current += 1
            max_concurrent = max(max_concurrent, current)
        await asyncio.sleep(0)
        async with lock:
            current -= 1

    ticker_service = MagicMock(spec=TickerService)
    ticker_service.fetch_ticker = tracking_fetch
    subs = [
        TickerSubscription(
            venue_id="kucoin",
            symbol=s,
            channel_id=TickerSubscription.make_channel_id("kucoin", s),
        )
        for s in ("BTC/USDT", "ETH/USDT", "SOL/USDT")
    ]
    worker = TickerSyncWorker(
        ticker_service=ticker_service,
        subscriber=_make_subscriber(subs),
    )
    await worker.sync_once()
    assert max_concurrent >= 2  # at least 2 overlapping fetches


@pytest.mark.asyncio
async def test_sync_once_propagates_cancellation() -> None:
    """CancelledError from the service must bubble up — not be swallowed by the catch-all."""
    ticker_service = MagicMock(spec=TickerService)
    ticker_service.fetch_ticker = AsyncMock(side_effect=asyncio.CancelledError())
    worker = TickerSyncWorker(
        ticker_service=ticker_service,
        subscriber=_make_subscriber(
            [
                TickerSubscription(
                    venue_id="kucoin",
                    symbol="BTC/USDT",
                    channel_id=TickerSubscription.make_channel_id("kucoin", "BTC/USDT"),
                )
            ]
        ),
    )
    with pytest.raises(asyncio.CancelledError):
        await worker.sync_once()


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
