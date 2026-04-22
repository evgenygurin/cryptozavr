"""Realtime subscriber for cryptozavr.tickers_live.

Wraps supabase-py AsyncClient's realtime channels. Each subscribe_*
call opens one channel filtered server-side by venue_id. close() tears
all channels down and closes the realtime connection.

Phase 1.5 adds per-symbol subscribe_ticker + subscriptions() accessor
so a TickerSyncWorker can periodically refresh the subscribed tickers.
The legacy subscribe_tickers (per-venue) stays for compatibility; it
does NOT populate subscriptions().

Note: the filter `venue_id=eq.<venue>` stays — tickers_live uses
symbol_id as PK and venue_id lives in the symbols join. The channel
still opens; downstream callback handles symbol-level routing.
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
    """Per-symbol ticker subscription record exposed via `subscriptions()`."""

    venue_id: str
    symbol: str
    channel_id: str


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
    ) -> SubscriptionHandle:
        """Open a filtered postgres_changes channel for a venue's tickers.

        Per-venue (legacy) subscription; does NOT populate `subscriptions()`.
        Use `subscribe_ticker(venue_id, symbol, callback)` for per-symbol
        tracking that TickerSyncWorker can refresh.
        """
        channel_id = f"cryptozavr-tickers-{venue_id}"
        await self._open_and_register(
            channel_id=channel_id,
            venue_id=venue_id,
            callback=callback,
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
    ) -> None:
        if self._client is None:
            raise RuntimeError(
                "RealtimeSubscriber initialised without a supabase client",
            )
        channel = self._client.channel(channel_id)
        channel.on_postgres_changes(
            event="*",
            schema="cryptozavr",
            table="tickers_live",
            filter=f"venue_id=eq.{venue_id}",
            callback=callback,
        )
        await channel.subscribe()
        self._channels[channel_id] = channel
