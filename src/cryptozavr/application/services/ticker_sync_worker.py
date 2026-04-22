"""TickerSyncWorker: periodic force-refresh of subscribed tickers."""

from __future__ import annotations

import asyncio
import logging

from cryptozavr.application.services.ticker_service import TickerService
from cryptozavr.infrastructure.supabase.realtime import RealtimeSubscriber


class TickerSyncWorker:
    """Background task keeping the L0 cache warm for subscribed tickers.

    Reads `RealtimeSubscriber.subscriptions()` each tick and calls
    `TickerService.fetch_ticker(force_refresh=True)` for every entry.
    No-op when there are no subscriptions, so it is safe to start
    unconditionally from the MCP lifespan.
    """

    def __init__(
        self,
        *,
        ticker_service: TickerService,
        subscriber: RealtimeSubscriber,
        interval_seconds: float = 30.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self._ticker_service = ticker_service
        self._subscriber = subscriber
        self._interval = interval_seconds
        self._logger = logger or logging.getLogger("cryptozavr.application.ticker_sync_worker")
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def sync_once(self) -> None:
        subs = self._subscriber.subscriptions()
        if not subs:
            return
        results = await asyncio.gather(
            *(
                self._ticker_service.fetch_ticker(
                    venue=sub.venue_id,
                    symbol=sub.symbol,
                    force_refresh=True,
                )
                for sub in subs
            ),
            return_exceptions=True,
        )
        for sub, result in zip(subs, results, strict=True):
            if isinstance(result, asyncio.CancelledError):
                raise result
            if isinstance(result, BaseException):
                self._logger.warning(
                    "ticker sync failed for %s/%s: %s",
                    sub.venue_id,
                    sub.symbol,
                    result,
                    exc_info=result,
                )

    async def start(self) -> None:
        if self.is_running:
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._run_forever(), name="cryptozavr-ticker-sync")

    async def stop(self) -> None:
        self._stopping.set()
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            self._logger.exception("ticker sync task raised during shutdown")

    async def _run_forever(self) -> None:
        while not self._stopping.is_set():
            try:
                await self.sync_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                self._logger.exception("ticker sync iteration crashed")
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
            except TimeoutError:
                continue
