"""Live WS smoke test. Gated by SKIP_LIVE_TESTS env var."""

from __future__ import annotations

import asyncio
import os
from decimal import Decimal

import pytest

from cryptozavr.application.services.position_watcher import PositionWatcher
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.domain.watch import WatchSide
from cryptozavr.infrastructure.providers.kucoin_ws import KucoinWsProvider

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("SKIP_LIVE_TESTS") == "1",
        reason="live WS skipped",
    ),
]


async def test_live_watch_receives_ticks() -> None:
    ws = KucoinWsProvider()
    try:
        reg = SymbolRegistry()
        btc = reg.get(
            VenueId.KUCOIN,
            "BTC",
            "USDT",
            market_type=MarketType.SPOT,
            native_symbol="BTC-USDT",
        )
        registry: dict = {}
        watcher = PositionWatcher(ws_provider=ws, registry=registry)
        watch_id = await watcher.start(
            symbol=btc,
            side=WatchSide.LONG,
            entry=Decimal("1"),
            stop=Decimal("0.5"),
            take=Decimal("1000000"),
            size_quote=None,
            max_duration_sec=60,
        )
        for _ in range(300):
            state = watcher.check(watch_id)
            if state.current_price is not None:
                break
            await asyncio.sleep(0.1)

        state = watcher.check(watch_id)
        assert state.current_price is not None, "no tick received"
        assert state.current_price > Decimal("1")

        final = await watcher.stop(watch_id)
        assert final.status.value == "cancelled"
    finally:
        await ws.close()
