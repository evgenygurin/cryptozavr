"""Realtime subscriptions wrapper — stub for M2.2.

Full implementation (postgres_changes subscriptions for tickers/decisions)
lands in phase 1.5 per MVP design spec section 11.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SubscriptionHandle:
    """Identifier for an active realtime subscription. Used to unsubscribe later."""

    channel_id: str


class RealtimeSubscriber:
    """Stub: raises NotImplementedError in M2.2. Replaced in phase 1.5."""

    def __init__(self) -> None:
        pass

    async def subscribe_tickers(
        self,
        venue_id: str,
        callback: object,
    ) -> SubscriptionHandle:
        raise NotImplementedError(
            "Realtime subscriptions arrive in phase 1.5; see MVP spec section 11."
        )

    async def close(self) -> None:
        return None
