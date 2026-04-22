"""MCP resources for paper trading: ledger, open_trades, stats, trades/{id}.

All resources return `ResourceResult(contents=[ResourceContent(..., mime_type=...)])`
following the project's established pattern in `catalogs.py` — required because
FastMCP v3 URI-template resources lose the decorator-level `mime_type` hint under
stdio transport, so clients see `text/plain` despite the decorator kwarg.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from fastmcp import FastMCP
from fastmcp.dependencies import Depends
from fastmcp.resources import ResourceContent, ResourceResult

from cryptozavr.domain.exceptions import TradeNotFoundError
from cryptozavr.infrastructure.persistence.paper_trade_repo import (
    PaperTradeRepository,
)
from cryptozavr.mcp.dtos import PaperStatsDTO, PaperTradeDTO
from cryptozavr.mcp.errors import domain_to_tool_error
from cryptozavr.mcp.lifespan_state import (
    get_paper_bankroll_override,
    get_paper_repo,
)

_REPO: PaperTradeRepository = Depends(get_paper_repo)
_OVERRIDE: dict[str, Any] = Depends(get_paper_bankroll_override)

_JSON_MIME = "application/json"


def _json_resource(payload: object) -> ResourceResult:
    """Wrap a JSON-serialisable payload in a single-content JSON ResourceResult."""
    return ResourceResult(
        contents=[
            ResourceContent(
                content=json.dumps(payload),
                mime_type=_JSON_MIME,
            ),
        ],
    )


def register_paper_resources(mcp: FastMCP, *, bankroll_initial: Decimal) -> None:
    """Attach paper-trading resources to the given FastMCP instance."""

    def _effective(override: dict[str, Any]) -> Decimal:
        value = override.get("value")
        if isinstance(value, Decimal):
            return value
        return bankroll_initial

    @mcp.resource(
        uri="cryptozavr://paper/ledger",
        name="paper_ledger",
        description="All paper trades, newest first (bounded 200).",
        mime_type=_JSON_MIME,
        tags={"paper"},
        annotations={"readOnlyHint": True, "idempotentHint": False},
    )
    async def ledger(repo: PaperTradeRepository = _REPO) -> ResourceResult:
        trades = await repo.fetch_page(limit=200, offset=0)
        total = await repo.count()
        payload = {
            "trades": [PaperTradeDTO.from_domain(t).model_dump(mode="json") for t in trades],
            "total_count": total,
            "returned": len(trades),
        }
        return _json_resource(payload)

    @mcp.resource(
        uri="cryptozavr://paper/open_trades",
        name="paper_open_trades",
        description="Only status='running' trades, newest first.",
        mime_type=_JSON_MIME,
        tags={"paper"},
        annotations={"readOnlyHint": True, "idempotentHint": False},
    )
    async def open_trades(repo: PaperTradeRepository = _REPO) -> ResourceResult:
        trades = await repo.fetch_open()
        payload = {
            "trades": [PaperTradeDTO.from_domain(t).model_dump(mode="json") for t in trades],
            "count": len(trades),
        }
        return _json_resource(payload)

    @mcp.resource(
        uri="cryptozavr://paper/stats",
        name="paper_stats",
        description="Aggregate paper-trading statistics + live bankroll.",
        mime_type=_JSON_MIME,
        tags={"paper"},
        annotations={"readOnlyHint": True, "idempotentHint": False},
    )
    async def stats(
        repo: PaperTradeRepository = _REPO,
        override: dict[str, Any] = _OVERRIDE,
    ) -> ResourceResult:
        s = await repo.stats()
        dto = PaperStatsDTO.from_stats(s, bankroll_initial=_effective(override))
        return _json_resource(dto.model_dump(mode="json"))

    @mcp.resource(
        uri="cryptozavr://paper/trades/{trade_id}",
        name="paper_trade_detail",
        description="Full snapshot of a single paper trade by id.",
        mime_type=_JSON_MIME,
        tags={"paper"},
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    async def trade_detail(
        trade_id: str,
        repo: PaperTradeRepository = _REPO,
    ) -> ResourceResult:
        try:
            trade = await repo.fetch_by_id(trade_id)
        except TradeNotFoundError as exc:
            raise domain_to_tool_error(exc) from exc
        if trade is None:
            raise domain_to_tool_error(TradeNotFoundError(trade_id=trade_id))
        dto = PaperTradeDTO.from_domain(trade)
        return _json_resource(dto.model_dump(mode="json"))
