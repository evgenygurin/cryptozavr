"""PaperLedgerService — orchestrates repository + watcher for paper trading."""

from __future__ import annotations

import contextlib
import logging
import time
from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Protocol
from uuid import uuid4

from cryptozavr.application.services.position_watcher import PositionWatcher
from cryptozavr.application.services.symbol_resolver import SymbolResolver
from cryptozavr.domain.exceptions import DomainError, TradeNotFoundError
from cryptozavr.domain.paper import PaperSide, PaperStatus, PaperTrade
from cryptozavr.domain.watch import WatchEvent, WatchSide

_LOG = logging.getLogger(__name__)


class _RepoProto(Protocol):
    async def insert(self, trade: PaperTrade) -> None: ...
    async def set_watch_id(self, trade_id: str, watch_id: str | None) -> None: ...
    async def close(
        self,
        *,
        trade_id: str,
        exit_price: Decimal,
        closed_at_ms: int,
        pnl_quote: Decimal,
        reason: str,
        target_status: PaperStatus = PaperStatus.CLOSED,
    ) -> int: ...
    async def fetch_by_id(self, trade_id: str) -> PaperTrade | None: ...
    async def fetch_open(self) -> list[PaperTrade]: ...
    async def mark_abandoned(self, trade_id: str, reason: str) -> int: ...


class PaperLedgerService:
    def __init__(
        self,
        *,
        repository: _RepoProto,
        watcher: PositionWatcher,
        resolver: SymbolResolver,
    ) -> None:
        self._repo = repository
        self._watcher = watcher
        self._resolver = resolver

    async def open_trade(
        self,
        *,
        venue: str,
        symbol: str,
        side: PaperSide,
        entry: Decimal,
        stop: Decimal,
        take: Decimal,
        size_quote: Decimal,
        max_duration_sec: int,
        note: str | None = None,
    ) -> PaperTrade:
        resolved = self._resolver.resolve(user_input=symbol, venue=venue)
        trade = PaperTrade(
            id=uuid4(),
            side=side,
            venue=venue,
            symbol_native=resolved.native_symbol,
            entry=entry,
            stop=stop,
            take=take,
            size_quote=size_quote,
            opened_at_ms=int(time.time() * 1000),
            max_duration_sec=max_duration_sec,
            status=PaperStatus.RUNNING,
            note=note,
        )
        await self._repo.insert(trade)

        try:
            watch_id = await self._watcher.start(
                symbol=resolved,
                side=WatchSide(side.value),
                entry=entry,
                stop=stop,
                take=take,
                size_quote=size_quote,
                max_duration_sec=max_duration_sec,
                on_terminal=self._make_terminal_handler(str(trade.id)),
            )
        except DomainError:
            await self._repo.mark_abandoned(str(trade.id), reason="watch_start_failed")
            raise

        await self._repo.set_watch_id(str(trade.id), watch_id)
        fresh = await self._repo.fetch_by_id(str(trade.id))
        assert fresh is not None
        return fresh

    async def close_trade(
        self,
        trade_id: str,
        *,
        exit_price: Decimal,
        reason: str = "manual_cancel",
    ) -> PaperTrade:
        current = await self._repo.fetch_by_id(trade_id)
        if current is None:
            raise TradeNotFoundError(trade_id=trade_id)
        if current.status is not PaperStatus.RUNNING:
            return current  # idempotent

        if current.watch_id is not None:
            with contextlib.suppress(DomainError):
                await self._watcher.stop(current.watch_id)

        pnl = current.compute_pnl(exit_price=exit_price)
        await self._repo.close(
            trade_id=trade_id,
            exit_price=exit_price,
            closed_at_ms=int(time.time() * 1000),
            pnl_quote=pnl,
            reason=reason,
        )
        fresh = await self._repo.fetch_by_id(trade_id)
        assert fresh is not None
        return fresh

    async def resume_open_watches(self) -> int:
        """Re-attach live watches for every status='running' row. Returns count."""
        open_trades = await self._repo.fetch_open()
        resumed = 0
        for trade in open_trades:
            try:
                resolved = self._resolver.resolve(user_input=trade.symbol_native, venue=trade.venue)
                new_watch_id = await self._watcher.start(
                    symbol=resolved,
                    side=WatchSide(trade.side.value),
                    entry=trade.entry,
                    stop=trade.stop,
                    take=trade.take,
                    size_quote=trade.size_quote,
                    max_duration_sec=trade.max_duration_sec,
                    on_terminal=self._make_terminal_handler(str(trade.id)),
                )
            except Exception as exc:
                _LOG.warning(
                    "resume failed for trade %s: %s — marking abandoned",
                    trade.id,
                    exc,
                )
                await self._repo.mark_abandoned(str(trade.id), reason=f"resume_failed: {exc}")
                continue
            await self._repo.set_watch_id(str(trade.id), new_watch_id)
            resumed += 1
        return resumed

    def _make_terminal_handler(self, trade_id: str) -> Callable[[str, WatchEvent], Awaitable[None]]:
        async def handler(watch_id: str, event: WatchEvent) -> None:
            trade = await self._repo.fetch_by_id(trade_id)
            if trade is None or trade.status is not PaperStatus.RUNNING:
                return
            pnl = trade.compute_pnl(exit_price=event.price)
            await self._repo.close(
                trade_id=trade_id,
                exit_price=event.price,
                closed_at_ms=event.ts_ms,
                pnl_quote=pnl,
                reason=event.type.value,
            )

        return handler
