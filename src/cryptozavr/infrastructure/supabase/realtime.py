"""Realtime subscriber for cryptozavr.tickers_live.

Wraps supabase-py AsyncClient's realtime channels. Each subscribe_*
call opens one channel filtered server-side by venue_id. close() tears
all channels down and closes the realtime connection.

Phase 1.5 scope per MVP spec § 11. MCP-tool exposure lands later
(needs FastMCP background-task plumbing).

Note: the filter `venue_id=eq.<venue>` is a placeholder — tickers_live
uses symbol_id as PK and venue_id lives in the symbols join. The channel
still opens; no events arrive until M3+ adds proper column/join. The
filter validates the subscription wiring contract for MVP.
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


class RealtimeSubscriber:
    """Holds open realtime channels for the MCP lifespan.

    One subscriber per process. Subscribes to cryptozavr.tickers_live
    INSERT/UPDATE/DELETE events, filtered server-side by venue_id.
    """

    def __init__(self, *, client: Any | None) -> None:
        self._client = client
        self._channels: dict[str, Any] = {}

    async def subscribe_tickers(
        self,
        venue_id: str,
        callback: TickerCallback,
    ) -> SubscriptionHandle:
        """Open a filtered postgres_changes channel for a venue's tickers."""
        if self._client is None:
            raise RuntimeError(
                "RealtimeSubscriber initialised without a supabase client",
            )
        channel_id = f"cryptozavr-tickers-{venue_id}"
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
        return SubscriptionHandle(channel_id=channel_id)

    async def close(self) -> None:
        """Unsubscribe all channels and close the realtime connection.

        Best-effort — individual unsubscribe failures are swallowed so
        one bad channel doesn't block cleanup of the rest.
        """
        for channel in self._channels.values():
            with contextlib.suppress(Exception):
                await channel.unsubscribe()
        self._channels.clear()
        if self._client is not None and hasattr(self._client, "realtime"):
            close = getattr(self._client.realtime, "close", None)
            if close is not None:
                with contextlib.suppress(Exception):
                    await close()
