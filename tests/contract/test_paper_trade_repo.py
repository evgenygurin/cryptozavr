"""Contract tests: PaperTradeRepository against live Supabase.

Skipped if SUPABASE_DB_URL is missing or SKIP_SUPABASE_TESTS=1.
"""

from __future__ import annotations

import os
from decimal import Decimal
from uuid import uuid4

import asyncpg
import pytest

from cryptozavr.domain.paper import PaperSide, PaperStatus, PaperTrade
from cryptozavr.infrastructure.persistence.paper_trade_repo import (
    PaperTradeRepository,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("SKIP_SUPABASE_TESTS") == "1" or not os.getenv("SUPABASE_DB_URL"),
        reason="live Supabase tests disabled",
    ),
]


async def _build_repo() -> tuple[PaperTradeRepository, asyncpg.Pool]:
    pool = await asyncpg.create_pool(os.environ["SUPABASE_DB_URL"], min_size=1, max_size=2)
    await pool.execute("truncate cryptozavr.paper_trades")
    return PaperTradeRepository(pool=pool), pool


def _sample_trade() -> PaperTrade:
    return PaperTrade(
        id=uuid4(),
        side=PaperSide.LONG,
        venue="kucoin",
        symbol_native="BTC-USDT",
        entry=Decimal("100"),
        stop=Decimal("95"),
        take=Decimal("110"),
        size_quote=Decimal("1000"),
        opened_at_ms=1_000_000,
        max_duration_sec=3600,
        status=PaperStatus.RUNNING,
    )


async def test_insert_fetch_roundtrip() -> None:
    repo, pool = await _build_repo()
    try:
        trade = _sample_trade()
        await repo.insert(trade)
        got = await repo.fetch_by_id(str(trade.id))
        assert got is not None
        assert got.id == trade.id
        assert got.status is PaperStatus.RUNNING
        assert got.watch_id is None
    finally:
        await pool.close()


async def test_set_watch_id() -> None:
    repo, pool = await _build_repo()
    try:
        trade = _sample_trade()
        await repo.insert(trade)
        await repo.set_watch_id(str(trade.id), "watch-abc")
        got = await repo.fetch_by_id(str(trade.id))
        assert got is not None
        assert got.watch_id == "watch-abc"
    finally:
        await pool.close()


async def test_close_atomic() -> None:
    repo, pool = await _build_repo()
    try:
        trade = _sample_trade()
        await repo.insert(trade)
        rowcount = await repo.close(
            trade_id=str(trade.id),
            exit_price=Decimal("110"),
            closed_at_ms=1_100_000,
            pnl_quote=Decimal("100"),
            reason="take_hit",
        )
        assert rowcount == 1
        # Second close is no-op (already closed).
        rowcount2 = await repo.close(
            trade_id=str(trade.id),
            exit_price=Decimal("105"),
            closed_at_ms=1_200_000,
            pnl_quote=Decimal("50"),
            reason="manual_cancel",
        )
        assert rowcount2 == 0
        got = await repo.fetch_by_id(str(trade.id))
        assert got is not None
        assert got.status is PaperStatus.CLOSED
        assert got.reason == "take_hit"
        assert got.pnl_quote == Decimal("100")
    finally:
        await pool.close()


async def test_fetch_open() -> None:
    repo, pool = await _build_repo()
    try:
        t1 = _sample_trade()
        t2 = _sample_trade()
        await repo.insert(t1)
        await repo.insert(t2)
        await repo.close(
            trade_id=str(t1.id),
            exit_price=Decimal("110"),
            closed_at_ms=1_100_000,
            pnl_quote=Decimal("100"),
            reason="take_hit",
        )
        open_trades = await repo.fetch_open()
        assert len(open_trades) == 1
        assert open_trades[0].id == t2.id
    finally:
        await pool.close()


async def test_stats_view() -> None:
    repo, pool = await _build_repo()
    try:
        # 2 closed trades: one winner, one loser. 1 running.
        for pnl, reason in [(Decimal("50"), "take_hit"), (Decimal("-30"), "stop_hit")]:
            trade = _sample_trade()
            await repo.insert(trade)
            await repo.close(
                trade_id=str(trade.id),
                exit_price=Decimal("100"),  # placeholder — only pnl matters for stats
                closed_at_ms=1_100_000,
                pnl_quote=pnl,
                reason=reason,
            )
        await repo.insert(_sample_trade())  # running
        stats = await repo.stats()
        assert stats.trades_count == 2
        assert stats.wins == 1
        assert stats.losses == 1
        assert stats.open_count == 1
        assert stats.net_pnl_quote == Decimal("20")
    finally:
        await pool.close()


async def test_truncate_removes_all() -> None:
    repo, pool = await _build_repo()
    try:
        await repo.insert(_sample_trade())
        await repo.truncate()
        open_trades = await repo.fetch_open()
        assert open_trades == []
    finally:
        await pool.close()
