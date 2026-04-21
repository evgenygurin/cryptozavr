"""Test RealtimeSubscriber: mocked supabase-py realtime client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from cryptozavr.infrastructure.supabase.realtime import (
    RealtimeSubscriber,
    SubscriptionHandle,
)


@pytest.fixture
def async_supabase_client():
    """Mocked supabase.AsyncClient exposing a chainable realtime channel."""
    client = MagicMock()
    channel = MagicMock()
    channel.on_postgres_changes = MagicMock(return_value=channel)
    channel.subscribe = AsyncMock()
    channel.unsubscribe = AsyncMock()
    client.channel = MagicMock(return_value=channel)
    client.realtime = MagicMock()
    client.realtime.close = AsyncMock()
    return client, channel


class TestRealtimeSubscriber:
    @pytest.mark.asyncio
    async def test_subscribe_tickers_opens_channel_for_venue(
        self,
        async_supabase_client,
    ) -> None:
        client, channel = async_supabase_client
        subscriber = RealtimeSubscriber(client=client)
        handle = await subscriber.subscribe_tickers(
            venue_id="kucoin",
            callback=lambda _: None,
        )
        assert isinstance(handle, SubscriptionHandle)
        assert "kucoin" in handle.channel_id
        client.channel.assert_called_once()
        channel.on_postgres_changes.assert_called_once()
        channel.subscribe.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_subscribe_filters_by_venue(
        self,
        async_supabase_client,
    ) -> None:
        client, channel = async_supabase_client
        subscriber = RealtimeSubscriber(client=client)
        await subscriber.subscribe_tickers(
            venue_id="coingecko",
            callback=lambda _: None,
        )
        _, kwargs = channel.on_postgres_changes.call_args
        assert "filter" in kwargs
        assert "venue_id=eq.coingecko" in kwargs["filter"]

    @pytest.mark.asyncio
    async def test_callback_is_wired_to_channel(
        self,
        async_supabase_client,
    ) -> None:
        client, channel = async_supabase_client
        received: list[object] = []

        def capture(payload: object) -> None:
            received.append(payload)

        subscriber = RealtimeSubscriber(client=client)
        await subscriber.subscribe_tickers(
            venue_id="kucoin",
            callback=capture,
        )
        # Grab the callback the subscriber registered — support either
        # positional last-arg or kwarg "callback".
        args = channel.on_postgres_changes.call_args.args
        kwargs = channel.on_postgres_changes.call_args.kwargs
        registered_callback = kwargs.get("callback")
        if registered_callback is None and args:
            registered_callback = args[-1]
        assert registered_callback is not None
        registered_callback({"record": {"venue_id": "kucoin"}})
        assert received == [{"record": {"venue_id": "kucoin"}}]

    @pytest.mark.asyncio
    async def test_close_unsubscribes_all_channels(
        self,
        async_supabase_client,
    ) -> None:
        client, channel = async_supabase_client
        subscriber = RealtimeSubscriber(client=client)
        await subscriber.subscribe_tickers(
            venue_id="kucoin",
            callback=lambda _: None,
        )
        await subscriber.subscribe_tickers(
            venue_id="coingecko",
            callback=lambda _: None,
        )
        await subscriber.close()
        assert channel.unsubscribe.await_count == 2
        client.realtime.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_subscribe_without_client_raises(self) -> None:
        subscriber = RealtimeSubscriber(client=None)
        with pytest.raises(RuntimeError):
            await subscriber.subscribe_tickers(
                venue_id="kucoin",
                callback=lambda _: None,
            )
