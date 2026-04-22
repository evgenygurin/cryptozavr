"""Live stack test: KuCoin WS + Supabase. Skipped by env flags."""

from __future__ import annotations

import asyncio
import os
from decimal import Decimal

import pytest

from cryptozavr.application.services.paper_ledger_service import PaperLedgerService
from cryptozavr.application.services.position_watcher import PositionWatcher
from cryptozavr.application.services.symbol_resolver import SymbolResolver
from cryptozavr.domain.paper import PaperSide, PaperStatus
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.persistence.paper_trade_repo import (
    PaperTradeRepository,
)
from cryptozavr.infrastructure.providers.kucoin_ws import KucoinWsProvider
from cryptozavr.infrastructure.supabase.pg_pool import PgPoolConfig, create_pool

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("SKIP_LIVE_TESTS") == "1"
        or os.getenv("SKIP_SUPABASE_TESTS") == "1"
        or not os.getenv("SUPABASE_DB_URL"),
        reason="live stack tests disabled",
    ),
]


async def test_open_and_manual_close_end_to_end() -> None:
    pool = await create_pool(PgPoolConfig(dsn=os.environ["SUPABASE_DB_URL"]))
    ws = KucoinWsProvider()
    try:
        await pool.execute("truncate cryptozavr.paper_trades")
        repo = PaperTradeRepository(pool=pool)
        reg = SymbolRegistry()
        reg.get(
            VenueId.KUCOIN,
            "BTC",
            "USDT",
            market_type=MarketType.SPOT,
            native_symbol="BTC-USDT",
        )
        resolver = SymbolResolver(reg)
        registry: dict = {}
        watcher = PositionWatcher(ws_provider=ws, registry=registry)
        ledger = PaperLedgerService(repository=repo, watcher=watcher, resolver=resolver)

        trade = await ledger.open_trade(
            venue="kucoin",
            symbol="BTC-USDT",
            side=PaperSide.LONG,
            entry=Decimal("1"),  # absurd so nothing hits
            stop=Decimal("0.5"),
            take=Decimal("1000000"),
            size_quote=Decimal("100"),
            max_duration_sec=120,
        )
        assert trade.status is PaperStatus.RUNNING
        assert trade.watch_id is not None

        state = registry[trade.watch_id]
        for _ in range(50):
            if state.current_price is not None:
                break
            await asyncio.sleep(0.1)
        assert state.current_price is not None

        closed = await ledger.close_trade(
            str(trade.id),
            exit_price=state.current_price,
            reason="manual_cancel",
        )
        assert closed.status is PaperStatus.CLOSED
        assert closed.reason == "manual_cancel"
        await pool.execute("delete from cryptozavr.paper_trades where id = $1", trade.id)
    finally:
        await ws.close()
        await pool.close()
