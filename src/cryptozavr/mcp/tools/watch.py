"""MCP tools for position watching: watch_position / check_watch / stop_watch / wait_for_event."""

from __future__ import annotations

import asyncio
import contextlib
from decimal import Decimal
from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.dependencies import Depends
from pydantic import Field

from cryptozavr.application.services.position_watcher import PositionWatcher
from cryptozavr.application.services.symbol_resolver import SymbolResolver
from cryptozavr.domain.exceptions import DomainError
from cryptozavr.domain.watch import WatchSide, WatchStatus
from cryptozavr.mcp.dtos import WatchIdDTO, WatchStateDTO
from cryptozavr.mcp.errors import domain_to_tool_error
from cryptozavr.mcp.lifespan_state import (
    get_position_watcher,
    get_symbol_resolver,
)

_RESOLVER: SymbolResolver = Depends(get_symbol_resolver)
_WATCHER: PositionWatcher = Depends(get_position_watcher)


def register_watch_tools(mcp: FastMCP) -> None:
    """Attach watch_position / check_watch / stop_watch / wait_for_event tools."""

    @mcp.tool(
        name="watch_position",
        description=(
            "Start a background position watch. Returns watch_id immediately. "
            "Polls real-time ticker via WebSocket and emits fire-once events "
            "(price_approaches_stop/take, breakeven_reached) plus terminal "
            "events (stop_hit/take_hit/timeout). Poll via check_watch or "
            "long-poll via wait_for_event."
        ),
        tags={"market", "position", "streaming"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def watch_position(
        venue: Annotated[str, Field(description="Venue id (only 'kucoin' in v1).")],
        symbol: Annotated[str, Field(description="Native symbol, e.g. BTC-USDT.")],
        side: Annotated[str, Field(description="'long' or 'short'.")],
        entry: Annotated[Decimal, Field(description="Entry price.")],
        stop: Annotated[Decimal, Field(description="Stop price.")],
        take: Annotated[Decimal, Field(description="Take-profit price.")],
        ctx: Context,
        size_quote: Annotated[
            Decimal | None,
            Field(description="Optional USD size (for absolute P&L)."),
        ] = None,
        max_duration_sec: Annotated[
            int,
            Field(ge=60, le=86_400, description="Max watch duration seconds."),
        ] = 3_600,
        resolver: SymbolResolver = _RESOLVER,
        watcher: PositionWatcher = _WATCHER,
    ) -> WatchIdDTO:
        await ctx.info(f"watch_position {venue}/{symbol} side={side}")
        try:
            resolved = resolver.resolve(user_input=symbol, venue=venue)
            watch_id = await watcher.start(
                symbol=resolved,
                side=WatchSide(side),
                entry=entry,
                stop=stop,
                take=take,
                size_quote=size_quote,
                max_duration_sec=max_duration_sec,
            )
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc
        state = watcher.check(watch_id)
        return WatchIdDTO.from_domain(state)

    @mcp.tool(
        name="check_watch",
        description=(
            "Snapshot of an active watch: current price, P&L, status, and "
            "events since the last check (pass next_event_index from the "
            "previous response as since_event_index)."
        ),
        tags={"market", "position", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def check_watch(
        watch_id: Annotated[str, Field(description="The watch id to inspect.")],
        ctx: Context,
        since_event_index: Annotated[
            int, Field(ge=0, description="Return events[since_event_index:].")
        ] = 0,
        watcher: PositionWatcher = _WATCHER,
    ) -> WatchStateDTO:
        await ctx.info(f"check_watch {watch_id}")
        try:
            state = watcher.check(watch_id)
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc
        return WatchStateDTO.from_domain(state, since_event_index=since_event_index)

    @mcp.tool(
        name="stop_watch",
        description="Cancel an active watch. Returns the final snapshot.",
        tags={"market", "position"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def stop_watch(
        watch_id: Annotated[str, Field(description="The watch id to cancel.")],
        ctx: Context,
        watcher: PositionWatcher = _WATCHER,
    ) -> WatchStateDTO:
        await ctx.info(f"stop_watch {watch_id}")
        try:
            state = await watcher.stop(watch_id)
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc
        return WatchStateDTO.from_domain(state)

    @mcp.tool(
        name="wait_for_event",
        description=(
            "Block up to `timeout_sec` until a new event appears, the watch "
            "terminates, or the timeout expires. Reaction on a real event: "
            "<100ms. \n"
            "\n"
            "USAGE PATTERN: short windows in a loop, not one giant call.\n"
            "  Example: /loop wait_for_event(watch_id, since_event_index=N, "
            "           timeout_sec=30)\n"
            "On empty return (status=running, events=[]) call again with the "
            "same since_event_index. On a new event the next_event_index in "
            "the response is your new cursor. On a terminal status, stop "
            "looping — the paper trade has been auto-closed.\n"
            "\n"
            "DO NOT pass timeout_sec > 60 unless you want the UI to show "
            "a giant spinner. The server keeps the watch running between "
            "calls; you lose nothing by polling short."
        ),
        tags={"market", "position", "streaming", "long-poll"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def wait_for_event(
        watch_id: Annotated[str, Field(description="The watch id to wait on.")],
        ctx: Context,
        since_event_index: Annotated[
            int,
            Field(
                ge=0,
                description=(
                    "Return events starting from this index. Pass the "
                    "next_event_index from the previous response to avoid "
                    "re-seeing earlier events."
                ),
            ),
        ] = 0,
        timeout_sec: Annotated[
            int,
            Field(
                ge=1,
                le=90,
                description=(
                    "Max seconds to block (default 30, max 90). Keep it short — "
                    "long polls past ~60s look frozen in the client UI. Re-invoke "
                    "the tool in a loop (`/loop wait_for_event`) instead."
                ),
            ),
        ] = 30,
        watcher: PositionWatcher = _WATCHER,
    ) -> WatchStateDTO:
        await ctx.info(
            f"wait_for_event {watch_id} since={since_event_index} timeout={timeout_sec}s"
        )
        try:
            state = watcher.check(watch_id)
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc

        cond = state.ensure_cond()

        def _ready() -> bool:
            return len(state.events) > since_event_index or state.status is not WatchStatus.RUNNING

        if not _ready():
            with contextlib.suppress(asyncio.TimeoutError):
                async with cond:
                    await asyncio.wait_for(cond.wait_for(_ready), timeout=timeout_sec)

        return WatchStateDTO.from_domain(state, since_event_index=since_event_index)
