"""MCP tools for paper trading: open, close, cancel, reset, set_bankroll."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from fastmcp import Context, FastMCP
from fastmcp.dependencies import Depends
from pydantic import Field

from cryptozavr.application.services.paper_ledger_service import PaperLedgerService
from cryptozavr.domain.exceptions import DomainError, ValidationError
from cryptozavr.domain.paper import PaperSide
from cryptozavr.infrastructure.persistence.paper_trade_repo import (
    PaperTradeRepository,
)
from cryptozavr.mcp.dtos import PaperStatsDTO, PaperTradeDTO
from cryptozavr.mcp.errors import domain_to_tool_error
from cryptozavr.mcp.lifespan_state import (
    get_paper_bankroll_override,
    get_paper_ledger,
    get_paper_repo,
)

_LEDGER: PaperLedgerService = Depends(get_paper_ledger)
_REPO = Depends(get_paper_repo)
_OVERRIDE = Depends(get_paper_bankroll_override)


def _effective_bankroll(initial: Decimal, override: dict[str, Any]) -> Decimal:
    value = override.get("value")
    if value is None:
        return initial
    return Decimal(value) if not isinstance(value, Decimal) else value


def register_paper_tools(mcp: FastMCP, *, bankroll_initial: Decimal) -> None:
    @mcp.tool(
        name="paper_open_trade",
        description=(
            "Open a paper trade. Persists to Supabase, starts a position watch "
            "automatically, returns the trade with assigned watch_id. A "
            "terminal event on the watch (stop_hit / take_hit / timeout) "
            "closes the trade atomically. Use check_watch / wait_for_event "
            "with the returned watch_id for live monitoring."
        ),
        tags={"paper", "position", "write"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def paper_open_trade(
        venue: Annotated[str, Field(description="Venue id (e.g. 'kucoin').")],
        symbol: Annotated[str, Field(description="Native symbol, e.g. BTC-USDT.")],
        side: Annotated[str, Field(description="'long' or 'short'.")],
        entry: Annotated[Decimal, Field(description="Entry price.")],
        stop: Annotated[Decimal, Field(description="Stop price.")],
        take: Annotated[Decimal, Field(description="Take profit price.")],
        size_quote: Annotated[
            Decimal, Field(description="Position size in quote currency (USDT).")
        ],
        ctx: Context,
        max_duration_sec: Annotated[int, Field(ge=60, le=86_400)] = 3_600,
        note: Annotated[str | None, Field(description="Optional free-form note.")] = None,
        ledger: PaperLedgerService = _LEDGER,
    ) -> PaperTradeDTO:
        await ctx.info(f"paper_open_trade {venue}/{symbol} {side} size={size_quote}")
        try:
            trade = await ledger.open_trade(
                venue=venue,
                symbol=symbol,
                side=PaperSide(side),
                entry=entry,
                stop=stop,
                take=take,
                size_quote=size_quote,
                max_duration_sec=max_duration_sec,
                note=note,
            )
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc
        return PaperTradeDTO.from_domain(trade)

    @mcp.tool(
        name="paper_close_trade",
        description=(
            "Close an open paper trade at a given exit price. Idempotent — "
            "closing an already-closed trade returns its current snapshot."
        ),
        tags={"paper", "position"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def paper_close_trade(
        trade_id: Annotated[str, Field(description="Trade uuid.")],
        exit_price: Annotated[Decimal, Field(description="Exit price.")],
        ctx: Context,
        reason: Annotated[str, Field(description="Close reason.")] = "manual_cancel",
        ledger: PaperLedgerService = _LEDGER,
    ) -> PaperTradeDTO:
        await ctx.info(f"paper_close_trade {trade_id} @ {exit_price}")
        try:
            trade = await ledger.close_trade(trade_id, exit_price=exit_price, reason=reason)
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc
        return PaperTradeDTO.from_domain(trade)

    @mcp.tool(
        name="paper_cancel_trade",
        description=(
            "Alias for paper_close_trade with reason='manual_cancel'. "
            "Requires explicit exit_price (fetch a fresh ticker first)."
        ),
        tags={"paper", "position"},
    )
    async def paper_cancel_trade(
        trade_id: Annotated[str, Field(description="Trade uuid.")],
        exit_price: Annotated[Decimal, Field(description="Exit price.")],
        ctx: Context,
        ledger: PaperLedgerService = _LEDGER,
    ) -> PaperTradeDTO:
        await ctx.info(f"paper_cancel_trade {trade_id}")
        try:
            trade = await ledger.close_trade(
                trade_id, exit_price=exit_price, reason="manual_cancel"
            )
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc
        return PaperTradeDTO.from_domain(trade)

    @mcp.tool(
        name="paper_reset",
        description=(
            "Wipe the paper-trading ledger. Requires confirm='RESET'. Also "
            "clears the bankroll override."
        ),
        tags={"paper", "write", "dangerous"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
        },
    )
    async def paper_reset(
        confirm: Annotated[str, Field(description="Must equal 'RESET' to proceed.")],
        ctx: Context,
        repo: PaperTradeRepository = _REPO,
        override: dict[str, Any] = _OVERRIDE,
    ) -> dict[str, Any]:
        if confirm != "RESET":
            raise domain_to_tool_error(ValidationError("confirm must equal 'RESET'"))
        await ctx.warning("paper_reset TRUNCATE")
        before = await repo.count()
        await repo.truncate()
        override["value"] = None
        return {"trades_deleted": before, "bankroll_initial": str(bankroll_initial)}

    @mcp.tool(
        name="paper_set_bankroll",
        description=(
            "Override the bankroll used for live-bankroll calculations "
            "(bankroll_initial + net_pnl_quote). Does NOT touch persisted "
            "trades. Pass a positive Decimal."
        ),
        tags={"paper", "config"},
    )
    async def paper_set_bankroll(
        bankroll: Annotated[Decimal, Field(description="New bankroll (>0).")],
        ctx: Context,
        repo: PaperTradeRepository = _REPO,
        override: dict[str, Any] = _OVERRIDE,
    ) -> PaperStatsDTO:
        if bankroll <= 0:
            raise domain_to_tool_error(ValidationError("bankroll must be positive"))
        override["value"] = bankroll
        stats = await repo.stats()
        return PaperStatsDTO.from_stats(stats, bankroll_initial=bankroll)
