"""Realtime subscriber for cryptozavr.tickers_live.

Wraps supabase-py AsyncClient's realtime channels. Each subscribe_*
call opens one channel filtered server-side by venue_id. close() tears
all channels down and closes the realtime connection.

Phase 1.5 adds per-symbol subscribe_ticker + subscriptions() accessor
so a TickerSyncWorker can periodically refresh the subscribed tickers.
The legacy subscribe_tickers (per-venue) stays for compatibility; it
does NOT populate subscriptions().

Note: `cryptozavr.tickers_live` has `symbol_id` as PK and no `venue_id`
column — Supabase Realtime filters are single-column, so a per-venue
filter is impossible without a schema change. The default filter is
therefore `None`; callers that need per-venue routing resolve the venue
inside their callback (CacheInvalidator does pessimistic all-venue
invalidation when the payload lacks a venue hint).
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

TickerCallback = Callable[[object], None]


@dataclass(frozen=True, slots=True)
class SubscriptionHandle:
    """Identifier for an active realtime subscription. Used to unsubscribe later."""

    channel_id: str


@dataclass(frozen=True, slots=True)
class TickerSubscription:
    """Per-symbol ticker subscription record exposed via `subscriptions()`.

    `channel_id` is derived from `(venue_id, symbol)` via `make_channel_id()`;
    callers should not pass an arbitrary string. The pattern is the single
    source of truth for routing realtime payloads back to providers.
    """

    venue_id: str
    symbol: str
    channel_id: str

    @staticmethod
    def make_channel_id(venue_id: str, symbol: str) -> str:
        return f"cryptozavr-ticker-{venue_id}-{symbol}"

    def __post_init__(self) -> None:
        expected = self.make_channel_id(self.venue_id, self.symbol)
        if self.channel_id != expected:
            raise ValueError(
                f"TickerSubscription.channel_id must be {expected!r}, got {self.channel_id!r}"
            )


class RealtimeSubscriber:
    """Holds open realtime channels for the MCP lifespan.

    One subscriber per process. Subscribes to cryptozavr.tickers_live
    INSERT/UPDATE/DELETE events, filtered server-side by venue_id.
    """

    def __init__(self, *, client: Any | None) -> None:
        self._client = client
        self._channels: dict[str, Any] = {}
        self._ticker_subscriptions: list[TickerSubscription] = []

    async def subscribe_tickers(
        self,
        venue_id: str,
        callback: TickerCallback,
        *,
        filter_expr: str | None = None,
    ) -> SubscriptionHandle:
        """Open a postgres_changes channel on cryptozavr.tickers_live.

        `venue_id` is kept as a label for the channel_id (so multiple
        subscribers can coexist), but since `tickers_live` has no
        `venue_id` column the default `filter_expr=None` subscribes to
        every row change. Callers that have a real filterable column
        (`symbol_id` after a schema change, for example) can pass it
        explicitly. Does NOT populate `subscriptions()` — use
        `subscribe_ticker(venue_id, symbol, callback)` for per-symbol
        tracking.
        """
        channel_id = f"cryptozavr-tickers-{venue_id}"
        await self._open_and_register(
            channel_id=channel_id,
            venue_id=venue_id,
            callback=callback,
            filter_expr=filter_expr,
        )
        return SubscriptionHandle(channel_id=channel_id)

    async def subscribe_ticker(
        self,
        *,
        venue_id: str,
        symbol: str,
        callback: TickerCallback,
    ) -> SubscriptionHandle:
        """Open a per-symbol subscription and remember it for periodic sync."""
        channel_id = f"cryptozavr-ticker-{venue_id}-{symbol}"
        await self._open_and_register(
            channel_id=channel_id,
            venue_id=venue_id,
            callback=callback,
            filter_expr=None,
        )
        self._ticker_subscriptions.append(
            TickerSubscription(
                venue_id=venue_id,
                symbol=symbol,
                channel_id=channel_id,
            )
        )
        return SubscriptionHandle(channel_id=channel_id)

    def subscriptions(self) -> list[TickerSubscription]:
        """Return a snapshot of currently-tracked per-symbol subscriptions."""
        return list(self._ticker_subscriptions)

    async def close(self) -> None:
        """Unsubscribe all channels and close the realtime connection.

        Best-effort — individual unsubscribe failures are swallowed so
        one bad channel doesn't block cleanup of the rest.
        """
        for channel in self._channels.values():
            with contextlib.suppress(Exception):
                await channel.unsubscribe()
        self._channels.clear()
        self._ticker_subscriptions.clear()
        if self._client is not None and hasattr(self._client, "realtime"):
            close = getattr(self._client.realtime, "close", None)
            if close is not None:
                with contextlib.suppress(Exception):
                    await close()

    async def _open_and_register(
        self,
        *,
        channel_id: str,
        venue_id: str,
        callback: TickerCallback,
        filter_expr: str | None = None,
    ) -> None:
        if self._client is None:
            raise RuntimeError(
                "RealtimeSubscriber initialised without a supabase client",
            )
        channel = self._client.channel(channel_id)
        kwargs: dict[str, object] = {
            "event": "*",
            "schema": "cryptozavr",
            "table": "tickers_live",
            "callback": callback,
        }
        if filter_expr is not None:
            kwargs["filter"] = filter_expr
        channel.on_postgres_changes(**kwargs)
        await channel.subscribe()
        self._channels[channel_id] = channel
