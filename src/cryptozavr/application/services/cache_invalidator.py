"""CacheInvalidator: bridges Supabase Realtime events to provider cache invalidation."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from cryptozavr.domain.venues import VenueId
from cryptozavr.infrastructure.supabase.realtime import (
    RealtimeSubscriber,
    SubscriptionHandle,
)


class CacheInvalidator:
    """Invalidates provider ticker caches when tickers_live rows change.

    `cryptozavr.tickers_live` stores `symbol_id` but no `venue_id`, and
    Supabase Realtime filters are single-column, so we subscribe without
    a filter and let the callback route events. When the payload exposes
    a venue hint (`record.venue_id` / `record.venue` / top-level
    `venue_id`) we invalidate just that provider; otherwise we fall back
    to pessimistic "invalidate every venue we know about" — safer than
    silently doing nothing, which was the previous behaviour.
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
        """Realtime callback. Classifies payload and invokes invalidation."""
        venues = self._resolve_target_venues(payload)
        if not venues:
            return
        for venue_id in venues:
            self._invalidate(venue_id)

    def _resolve_target_venues(self, payload: Any) -> list[VenueId]:
        if not isinstance(payload, dict):
            return []
        venue_label = self._extract_venue_id(payload)
        if venue_label is not None:
            try:
                return [VenueId(venue_label)]
            except ValueError:
                self._logger.debug("unknown venue_id in realtime payload: %s", venue_label)
                return []
        # No venue hint — pessimistic invalidation across all providers.
        return list(self._providers.keys())

    def _invalidate(self, venue_id: VenueId) -> None:
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
            except asyncio.CancelledError:
                raise
            except Exception:
                self._logger.exception("failed to subscribe realtime tickers for %s", venue_id)
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
