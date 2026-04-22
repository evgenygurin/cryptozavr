"""CacheInvalidator: bridges Supabase Realtime events to provider cache invalidation."""

from __future__ import annotations

import logging
from typing import Any

from cryptozavr.domain.venues import VenueId
from cryptozavr.infrastructure.supabase.realtime import (
    RealtimeSubscriber,
    SubscriptionHandle,
)


class CacheInvalidator:
    """Invalidates per-venue ticker caches when tickers_live rows change.

    Subscribes with `RealtimeSubscriber.subscribe_tickers` for each known
    venue. On every incoming payload, it resolves the venue_id from the
    row and calls `invalidate_tickers()` on the provider wrapped around
    an `InMemoryCachingDecorator`. Missing attributes fall through to a
    debug log so an incomplete wiring does not crash the process.
    """

    def __init__(
        self,
        *,
        subscriber: RealtimeSubscriber,
        providers: dict[VenueId, Any],
        logger: logging.Logger | None = None,
    ) -> None:
        self._subscriber = subscriber
        self._providers = providers
        self._logger = logger or logging.getLogger("cryptozavr.application.cache_invalidator")
        self._handles: list[SubscriptionHandle] = []

    def on_ticker_change(self, payload: Any) -> None:
        """Realtime callback entry point. Swallows errors to protect the loop."""
        venue_label = self._extract_venue_id(payload)
        if venue_label is None:
            self._logger.debug("realtime payload without venue_id: %r", payload)
            return
        try:
            venue_id = VenueId(venue_label)
        except ValueError:
            self._logger.debug("unknown venue_id in realtime payload: %s", venue_label)
            return
        provider = self._providers.get(venue_id)
        if provider is None:
            return
        invalidate = getattr(provider, "invalidate_tickers", None)
        if not callable(invalidate):
            return
        try:
            invalidate()
        except Exception:
            self._logger.exception("cache invalidation failed for %s", venue_id)

    async def start(self) -> None:
        """Open per-venue tickers subscriptions, routing events to the callback."""
        if self._handles:
            return
        for venue_id in self._providers:
            try:
                handle = await self._subscriber.subscribe_tickers(
                    venue_id=str(venue_id),
                    callback=self.on_ticker_change,
                )
            except Exception:
                self._logger.warning("failed to subscribe realtime tickers for %s", venue_id)
                continue
            self._handles.append(handle)

    async def stop(self) -> None:
        """Clear local subscription handles (subscriber owns channel teardown)."""
        self._handles.clear()

    @staticmethod
    def _extract_venue_id(payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return None
        record = payload.get("record") or payload.get("data") or {}
        if isinstance(record, dict):
            value = record.get("venue_id") or record.get("venue")
            if isinstance(value, str):
                return value
        direct = payload.get("venue_id")
        if isinstance(direct, str):
            return direct
        return None
