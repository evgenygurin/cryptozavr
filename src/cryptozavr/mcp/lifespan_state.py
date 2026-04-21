"""Canonical lifespan-dict keys + Depends accessors.

Per FastMCP v3 convention, the lifespan `yield`s a `dict` which
becomes `ctx.lifespan_context`. Tools access state via
`Depends(get_xxx_service)` + `CurrentContext()` — dependency params
are hidden from the MCP schema and automatically resolved at tool-
call time.

See: https://gofastmcp.com/servers/dependency-injection
     https://gofastmcp.com/servers/lifespan
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from fastmcp.dependencies import CurrentContext

if TYPE_CHECKING:
    from cryptozavr.application.services.discovery_service import DiscoveryService
    from cryptozavr.application.services.ohlcv_service import OhlcvService
    from cryptozavr.application.services.order_book_service import (
        OrderBookService,
    )
    from cryptozavr.application.services.symbol_resolver import SymbolResolver
    from cryptozavr.application.services.ticker_service import TickerService
    from cryptozavr.application.services.trades_service import TradesService
    from cryptozavr.domain.symbols import SymbolRegistry
    from cryptozavr.infrastructure.supabase.realtime import RealtimeSubscriber


@dataclass(frozen=True, slots=True)
class _LifespanKeys:
    """String constants for lifespan dict keys — guards against typos."""

    ticker_service: str = "ticker_service"
    ohlcv_service: str = "ohlcv_service"
    order_book_service: str = "order_book_service"
    trades_service: str = "trades_service"
    subscriber: str = "subscriber"
    symbol_resolver: str = "symbol_resolver"
    discovery_service: str = "discovery_service"
    registry: str = "registry"


LIFESPAN_KEYS = _LifespanKeys()

# Module-level singleton — avoids B008 (function call in default argument).
_CTX = CurrentContext()


def get_ticker_service(ctx: Any = _CTX) -> TickerService:
    return cast("TickerService", ctx.lifespan_context[LIFESPAN_KEYS.ticker_service])


def get_ohlcv_service(ctx: Any = _CTX) -> OhlcvService:
    return cast("OhlcvService", ctx.lifespan_context[LIFESPAN_KEYS.ohlcv_service])


def get_order_book_service(ctx: Any = _CTX) -> OrderBookService:
    return cast("OrderBookService", ctx.lifespan_context[LIFESPAN_KEYS.order_book_service])


def get_trades_service(ctx: Any = _CTX) -> TradesService:
    return cast("TradesService", ctx.lifespan_context[LIFESPAN_KEYS.trades_service])


def get_subscriber(ctx: Any = _CTX) -> RealtimeSubscriber:
    return cast("RealtimeSubscriber", ctx.lifespan_context[LIFESPAN_KEYS.subscriber])


def get_symbol_resolver(ctx: Any = _CTX) -> SymbolResolver:
    return cast("SymbolResolver", ctx.lifespan_context[LIFESPAN_KEYS.symbol_resolver])


def get_discovery_service(ctx: Any = _CTX) -> DiscoveryService:
    return cast("DiscoveryService", ctx.lifespan_context[LIFESPAN_KEYS.discovery_service])


def get_registry(ctx: Any = _CTX) -> SymbolRegistry:
    return cast("SymbolRegistry", ctx.lifespan_context[LIFESPAN_KEYS.registry])
