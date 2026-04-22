"""fetch_ohlcv_history MCP tool — streams large historical OHLCV windows.

Wraps OHLCVPaginator with ctx.report_progress between chunks and
SessionExplainer envelope output. Candles are accumulated in memory
and returned as a single OHLCVHistoryDTO embedded in the envelope.
For very long windows the caller is responsible for sizing
`since_ms`/`until_ms` to fit MCP response limits.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import Context, FastMCP
from fastmcp.dependencies import Depends
from pydantic import Field

from cryptozavr import __version__
from cryptozavr.application.services.ohlcv_paginator import OHLCVPaginator
from cryptozavr.application.services.ohlcv_service import OhlcvService
from cryptozavr.domain.exceptions import DomainError, ValidationError
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.mcp.dtos import OHLCVCandleDTO, OHLCVHistoryDTO
from cryptozavr.mcp.errors import domain_to_tool_error
from cryptozavr.mcp.explainer import build_envelope, new_query_id
from cryptozavr.mcp.lifespan_state import get_ohlcv_service

_REASON_CODE_LOG_LIMIT = 5

# Module-level singleton — avoids B008 (function call in default argument).
_OHLCV_SVC: OhlcvService = Depends(get_ohlcv_service)


def _parse_timeframe(raw: str) -> Timeframe:
    try:
        return Timeframe(raw)
    except ValueError as exc:
        raise domain_to_tool_error(
            ValidationError(f"unknown timeframe: {raw!r}"),
        ) from exc


def register_fetch_ohlcv_history_tool(mcp: FastMCP) -> None:
    """Attach fetch_ohlcv_history tool."""

    @mcp.tool(
        name="fetch_ohlcv_history",
        description=(
            "Stream OHLCV candles across a [since_ms, until_ms) window in "
            "chunks via OHLCVPaginator. Emits progress updates after each "
            "chunk. Returns a SessionExplainer envelope: "
            "{data: OHLCVHistoryDTO, quality, reasoning}. For very long "
            "windows consider chunk_size=500..1000; KuCoin caps each "
            "upstream call at 1500."
        ),
        tags={"market", "history", "public", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
        timeout=180.0,
        meta={"mode": "history", "version": __version__},
    )
    async def fetch_ohlcv_history(
        venue: Annotated[
            str,
            Field(description="Venue id. Supported: kucoin, coingecko."),
        ],
        symbol: Annotated[
            str,
            Field(description="Native symbol, e.g. BTC-USDT (kucoin)."),
        ],
        timeframe: Annotated[
            str,
            Field(description="Timeframe code: 1m, 5m, 15m, 1h, 4h, 1d."),
        ],
        since_ms: Annotated[
            int,
            Field(ge=0, description="Window start (Unix ms, inclusive)."),
        ],
        until_ms: Annotated[
            int,
            Field(ge=0, description="Window end (Unix ms, exclusive)."),
        ],
        ctx: Context,
        chunk_size: Annotated[
            int,
            Field(ge=1, le=1500, description="Candles per upstream fetch."),
        ] = 500,
        force_refresh: Annotated[
            bool,
            Field(description="Bypass the Supabase cache."),
        ] = False,
        service: OhlcvService = _OHLCV_SVC,
    ) -> dict[str, Any]:
        tf = _parse_timeframe(timeframe)
        if until_ms <= since_ms:
            raise domain_to_tool_error(
                ValidationError("until_ms must be strictly greater than since_ms"),
            )

        query_id = new_query_id()
        await ctx.info(
            f"fetch_ohlcv_history venue={venue} symbol={symbol} tf={timeframe} "
            f"since={since_ms} until={until_ms} chunk={chunk_size} qid={query_id}",
        )

        paginator = OHLCVPaginator(
            service=service,
            venue=venue,
            symbol=symbol,
            timeframe=tf,
            since_ms=since_ms,
            until_ms=until_ms,
            chunk_size=chunk_size,
            force_refresh=force_refresh,
        )
        total_chunks = paginator.total_chunks_estimate()
        candles: list[OHLCVCandleDTO] = []
        reason_codes: list[str] = []
        chunks_fetched = 0
        quality = None

        await ctx.report_progress(
            progress=0,
            total=total_chunks,
            message=f"starting (est. {total_chunks} chunks)",
        )
        try:
            async for chunk in paginator:
                chunks_fetched += 1
                for raw in chunk.series.candles:
                    candles.append(OHLCVCandleDTO.from_domain(raw))
                reason_codes.extend(chunk.reason_codes)
                # Capture quality from the latest chunk — freshness of the
                # most recent upstream read is the most useful signal.
                quality = chunk.series.quality
                await ctx.report_progress(
                    progress=min(chunks_fetched, total_chunks),
                    total=total_chunks,
                    message=f"chunk {chunks_fetched} ({len(candles)} candles)",
                )
        except DomainError as exc:
            raise domain_to_tool_error(exc) from exc

        dto = OHLCVHistoryDTO.from_chunks(
            venue=venue,
            symbol=symbol,
            timeframe=timeframe,
            range_start_ms=since_ms,
            range_end_ms=until_ms,
            candles=candles,
            chunks_fetched=chunks_fetched,
            reason_codes=reason_codes,
        )
        await ctx.report_progress(
            progress=total_chunks,
            total=total_chunks,
            message=f"done ({len(candles)} candles across {chunks_fetched} chunks)",
        )
        shown_codes = reason_codes[:_REASON_CODE_LOG_LIMIT]
        truncated = "..." if len(reason_codes) > _REASON_CODE_LOG_LIMIT else ""
        await ctx.info(
            f"fetch_ohlcv_history qid={query_id} chunks={chunks_fetched} "
            f"candles={len(candles)} codes={','.join(shown_codes)}{truncated}",
        )
        return build_envelope(
            data=dto,
            quality=quality,
            reason_codes=reason_codes,
            query_id=query_id,
        )
