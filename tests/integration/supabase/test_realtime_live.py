"""Live integration test for RealtimeSubscriber against cloud Supabase.

Skip-safe: requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY.
Opens a postgres_changes channel for `cryptozavr.tickers_live`
filtered by venue_id, waits briefly for any existing traffic, then
tears down cleanly. Confirms the subscriber-gateway wiring works
end-to-end against a real publication.
"""

from __future__ import annotations

import asyncio
import os

import pytest
from supabase import acreate_client

from cryptozavr.infrastructure.supabase.realtime import RealtimeSubscriber

pytestmark = pytest.mark.integration


_REQUIRED_ENV = ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")


@pytest.fixture(autouse=True)
def _skip_if_no_cloud_supabase() -> None:
    missing = [v for v in _REQUIRED_ENV if not os.getenv(v)]
    if missing:
        pytest.skip(f"missing env: {', '.join(missing)}")


@pytest.mark.asyncio
async def test_realtime_subscribe_and_close() -> None:
    """Open a channel, confirm no crash, close cleanly.

    Payload delivery is intentionally not asserted — that requires the
    full upsert path (M2.5 test_get_ticker_full_stack...). This test
    isolates the subscribe/close lifecycle.
    """
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    client = await acreate_client(url, key)
    subscriber = RealtimeSubscriber(client=client)
    received: list[object] = []

    def capture(payload: object) -> None:
        received.append(payload)

    try:
        handle = await subscriber.subscribe_tickers(
            venue_id="kucoin",
            callback=capture,
        )
        assert "kucoin" in handle.channel_id
        # Brief wait to let the channel establish — without this, close()
        # could race with the subscribe() completion.
        await asyncio.sleep(1.0)
    finally:
        await subscriber.close()

    # received may be empty (no traffic during this window) — that's OK.
    # The goal is confirming subscribe + close don't raise.
    assert isinstance(received, list)
