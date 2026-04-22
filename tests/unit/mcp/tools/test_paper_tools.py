from __future__ import annotations

import asyncio
import dataclasses
from contextlib import asynccontextmanager
from decimal import Decimal
from uuid import UUID

import pytest
from fastmcp import Client, FastMCP

from cryptozavr.application.services.paper_ledger_service import PaperLedgerService
from cryptozavr.application.services.position_watcher import PositionWatcher
from cryptozavr.application.services.symbol_resolver import SymbolResolver
from cryptozavr.domain.paper import PaperStats, PaperStatus, PaperTrade
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.mcp.lifespan_state import LIFESPAN_KEYS
from cryptozavr.mcp.tools.paper import register_paper_tools


class _StubWs:
    async def watch_ticker(self, _native: str):
        await asyncio.Event().wait()
        yield


class _FakeRepo:
    def __init__(self) -> None:
        self.rows: dict[UUID, PaperTrade] = {}

    async def insert(self, trade):
        self.rows[trade.id] = trade

    async def set_watch_id(self, trade_id, watch_id):
        tid = UUID(trade_id)
        current = self.rows[tid]
        self.rows[tid] = dataclasses.replace(current, watch_id=watch_id)

    async def close(
        self,
        *,
        trade_id,
        exit_price,
        closed_at_ms,
        pnl_quote,
        reason,
        target_status=None,
    ):
        tid = UUID(trade_id)
        current = self.rows[tid]
        if current.status is not PaperStatus.RUNNING:
            return 0
        self.rows[tid] = dataclasses.replace(
            current,
            status=PaperStatus.CLOSED,
            exit_price=exit_price,
            closed_at_ms=closed_at_ms,
            pnl_quote=pnl_quote,
            reason=reason,
        )
        return 1

    async def fetch_by_id(self, trade_id):
        return self.rows.get(UUID(trade_id))

    async def fetch_open(self):
        return [t for t in self.rows.values() if t.status is PaperStatus.RUNNING]

    async def fetch_page(self, limit=200, offset=0):
        return list(self.rows.values())[offset : offset + limit]

    async def count(self):
        return len(self.rows)

    async def mark_abandoned(self, trade_id, reason):
        tid = UUID(trade_id)
        current = self.rows[tid]
        self.rows[tid] = dataclasses.replace(current, status=PaperStatus.ABANDONED, reason=reason)
        return 1

    async def truncate(self):
        self.rows.clear()

    async def stats(self):
        return PaperStats(
            trades_count=0,
            wins=0,
            losses=0,
            open_count=len(self.rows),
            net_pnl_quote=Decimal("0"),
            avg_win_quote=Decimal("0"),
            avg_loss_quote=Decimal("0"),
        )


@pytest.fixture
def mcp_server():
    reg = SymbolRegistry()
    reg.get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )
    resolver = SymbolResolver(reg)
    watch_registry: dict = {}
    watcher = PositionWatcher(ws_provider=_StubWs(), registry=watch_registry)
    repo = _FakeRepo()
    ledger = PaperLedgerService(repository=repo, watcher=watcher, resolver=resolver)
    bankroll_override: dict = {"value": None}

    @asynccontextmanager
    async def lifespan(_server):
        yield {
            LIFESPAN_KEYS.paper_repo: repo,
            LIFESPAN_KEYS.paper_ledger: ledger,
            LIFESPAN_KEYS.paper_bankroll_override: bankroll_override,
        }

    mcp = FastMCP("test", lifespan=lifespan)
    register_paper_tools(mcp, bankroll_initial=Decimal("10000"))
    return mcp


async def test_open_trade_returns_dto(mcp_server) -> None:
    async with Client(mcp_server) as client:
        r = await client.call_tool(
            "paper_open_trade",
            {
                "venue": "kucoin",
                "symbol": "BTC-USDT",
                "side": "long",
                "entry": "100",
                "stop": "95",
                "take": "110",
                "size_quote": "1000",
                "max_duration_sec": 3600,
            },
        )
        assert r.structured_content["status"] == "running"
        assert r.structured_content["watch_id"]
        tid = r.structured_content["id"]
        await client.call_tool(
            "paper_close_trade",
            {"trade_id": tid, "exit_price": "101", "reason": "manual_cancel"},
        )


async def test_close_trade_idempotent(mcp_server) -> None:
    async with Client(mcp_server) as client:
        opened = await client.call_tool(
            "paper_open_trade",
            {
                "venue": "kucoin",
                "symbol": "BTC-USDT",
                "side": "long",
                "entry": "100",
                "stop": "95",
                "take": "110",
                "size_quote": "1000",
                "max_duration_sec": 3600,
            },
        )
        tid = opened.structured_content["id"]
        first = await client.call_tool(
            "paper_close_trade",
            {"trade_id": tid, "exit_price": "101", "reason": "manual_cancel"},
        )
        assert first.structured_content["status"] == "closed"
        second = await client.call_tool(
            "paper_close_trade",
            {"trade_id": tid, "exit_price": "105", "reason": "manual_cancel"},
        )
        assert second.structured_content["status"] == "closed"
        assert second.structured_content["exit_price"] == "101"


async def test_reset_requires_confirm(mcp_server) -> None:
    async with Client(mcp_server) as client:
        with pytest.raises(Exception, match="RESET"):
            await client.call_tool("paper_reset", {"confirm": "no"})


async def test_set_bankroll_updates_override(mcp_server) -> None:
    async with Client(mcp_server) as client:
        r = await client.call_tool("paper_set_bankroll", {"bankroll": "5000"})
        assert Decimal(r.structured_content["bankroll_initial"]) == Decimal("5000")
