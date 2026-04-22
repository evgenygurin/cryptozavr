"""PaperTradeRepository: asyncpg persistence for cryptozavr.paper_trades."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import asyncpg

from cryptozavr.domain.paper import (
    PaperSide,
    PaperStats,
    PaperStatus,
    PaperTrade,
)


class PaperTradeRepository:
    """CRUD for cryptozavr.paper_trades plus stats-view read."""

    def __init__(self, *, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def insert(self, trade: PaperTrade) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                insert into cryptozavr.paper_trades
                  (id, side, venue, symbol_native, entry, stop, take,
                   size_quote, opened_at_ms, max_duration_sec, status,
                   exit_price, closed_at_ms, pnl_quote, reason,
                   watch_id, note)
                values ($1, $2, $3, $4, $5, $6, $7,
                        $8, $9, $10, $11,
                        $12, $13, $14, $15,
                        $16, $17)
                """,
                trade.id,
                trade.side.value,
                trade.venue,
                trade.symbol_native,
                trade.entry,
                trade.stop,
                trade.take,
                trade.size_quote,
                trade.opened_at_ms,
                trade.max_duration_sec,
                trade.status.value,
                trade.exit_price,
                trade.closed_at_ms,
                trade.pnl_quote,
                trade.reason,
                trade.watch_id,
                trade.note,
            )

    async def set_watch_id(self, trade_id: str, watch_id: str | None) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "update cryptozavr.paper_trades set watch_id = $1 where id = $2",
                watch_id,
                UUID(trade_id),
            )

    async def close(
        self,
        *,
        trade_id: str,
        exit_price: Decimal,
        closed_at_ms: int,
        pnl_quote: Decimal,
        reason: str,
        target_status: PaperStatus = PaperStatus.CLOSED,
    ) -> int:
        """Atomic close — returns rowcount (1 on success, 0 if not running)."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                update cryptozavr.paper_trades
                set status = $1,
                    exit_price = $2,
                    closed_at_ms = $3,
                    pnl_quote = $4,
                    reason = $5
                where id = $6 and status = 'running'
                """,
                target_status.value,
                exit_price,
                closed_at_ms,
                pnl_quote,
                reason,
                UUID(trade_id),
            )
        # asyncpg returns 'UPDATE N'
        return int(result.split()[-1])

    async def mark_abandoned(self, trade_id: str, reason: str) -> int:
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                update cryptozavr.paper_trades
                set status = 'abandoned', reason = $1
                where id = $2 and status = 'running'
                """,
                reason,
                UUID(trade_id),
            )
        return int(result.split()[-1])

    async def fetch_by_id(self, trade_id: str) -> PaperTrade | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "select * from cryptozavr.paper_trades where id = $1",
                UUID(trade_id),
            )
        return _row_to_trade(row) if row else None

    async def fetch_open(self) -> list[PaperTrade]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "select * from cryptozavr.paper_trades where status = 'running'"
                " order by opened_at_ms desc"
            )
        return [_row_to_trade(r) for r in rows]

    async def fetch_page(self, limit: int = 200, offset: int = 0) -> list[PaperTrade]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "select * from cryptozavr.paper_trades"
                " order by opened_at_ms desc limit $1 offset $2",
                limit,
                offset,
            )
        return [_row_to_trade(r) for r in rows]

    async def count(self) -> int:
        async with self._pool.acquire() as conn:
            value = await conn.fetchval("select count(*) from cryptozavr.paper_trades")
        return int(value)

    async def stats(self) -> PaperStats:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("select * from cryptozavr.paper_stats")
        assert row is not None  # the view always returns a row
        return PaperStats(
            trades_count=row["trades_count"],
            wins=row["wins"],
            losses=row["losses"],
            open_count=row["open_count"],
            net_pnl_quote=row["net_pnl_quote"],
            avg_win_quote=row["avg_win_quote"],
            avg_loss_quote=row["avg_loss_quote"],
        )

    async def truncate(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("truncate cryptozavr.paper_trades")


def _row_to_trade(row: asyncpg.Record) -> PaperTrade:
    return PaperTrade(
        id=row["id"],
        side=PaperSide(row["side"]),
        venue=row["venue"],
        symbol_native=row["symbol_native"],
        entry=row["entry"],
        stop=row["stop"],
        take=row["take"],
        size_quote=row["size_quote"],
        opened_at_ms=row["opened_at_ms"],
        max_duration_sec=row["max_duration_sec"],
        status=PaperStatus(row["status"]),
        exit_price=row["exit_price"],
        closed_at_ms=row["closed_at_ms"],
        pnl_quote=row["pnl_quote"],
        reason=row["reason"],
        watch_id=row["watch_id"],
        note=row["note"],
    )
