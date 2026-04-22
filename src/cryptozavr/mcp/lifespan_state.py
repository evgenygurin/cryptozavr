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
    from cryptozavr.application.risk.engine import RiskEngine
    from cryptozavr.application.risk.kill_switch import KillSwitch
    from cryptozavr.application.services.analytics_service import AnalyticsService
    from cryptozavr.application.services.discovery_service import DiscoveryService
    from cryptozavr.application.services.ohlcv_service import OhlcvService
    from cryptozavr.application.services.order_book_service import (
        OrderBookService,
    )
    from cryptozavr.application.services.paper_ledger_service import (
        PaperLedgerService,
    )
    from cryptozavr.application.services.position_watcher import PositionWatcher
    from cryptozavr.application.services.symbol_resolver import SymbolResolver
    from cryptozavr.application.services.ticker_service import TickerService
    from cryptozavr.application.services.trades_service import TradesService
    from cryptozavr.domain.symbols import SymbolRegistry
    from cryptozavr.domain.venues import VenueId
    from cryptozavr.domain.watch import WatchState
    from cryptozavr.infrastructure.persistence.paper_trade_repo import (
        PaperTradeRepository,
    )
    from cryptozavr.infrastructure.persistence.risk_policy_repo import (
        RiskPolicyRepository,
    )
    from cryptozavr.infrastructure.persistence.strategy_spec_repo import (
        StrategySpecRepository,
    )
    from cryptozavr.infrastructure.providers.kucoin_ws import KucoinWsProvider
    from cryptozavr.infrastructure.providers.state.venue_state import VenueState
    from cryptozavr.infrastructure.supabase.realtime import RealtimeSubscriber


@dataclass(frozen=True, slots=True)
class _LifespanKeys:
    """String constants for lifespan dict keys — guards against typos."""

    ticker_service: str = "ticker_service"
    ohlcv_service: str = "ohlcv_service"
    order_book_service: str = "order_book_service"
    trades_service: str = "trades_service"
    analytics_service: str = "analytics_service"
    subscriber: str = "subscriber"
    symbol_resolver: str = "symbol_resolver"
    discovery_service: str = "discovery_service"
    registry: str = "registry"
    venue_states: str = "venue_states"
    metrics_registry: str = "metrics_registry"
    health_monitor: str = "health_monitor"
    ticker_sync_worker: str = "ticker_sync_worker"
    cache_invalidator: str = "cache_invalidator"
    strategy_spec_repo: str = "strategy_spec_repo"
    risk_policy_repo: str = "risk_policy_repo"
    risk_engine: str = "risk_engine"
    kill_switch: str = "kill_switch"
    ws_provider: str = "ws_provider"
    position_watcher: str = "position_watcher"
    watch_registry: str = "watch_registry"
    paper_repo: str = "paper_repo"
    paper_ledger: str = "paper_ledger"
    paper_bankroll_override: str = "paper_bankroll_override"
    providers: str = "providers"


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


def get_analytics_service(ctx: Any = _CTX) -> AnalyticsService:
    return cast("AnalyticsService", ctx.lifespan_context[LIFESPAN_KEYS.analytics_service])


def get_subscriber(ctx: Any = _CTX) -> RealtimeSubscriber:
    return cast("RealtimeSubscriber", ctx.lifespan_context[LIFESPAN_KEYS.subscriber])


def get_symbol_resolver(ctx: Any = _CTX) -> SymbolResolver:
    return cast("SymbolResolver", ctx.lifespan_context[LIFESPAN_KEYS.symbol_resolver])


def get_discovery_service(ctx: Any = _CTX) -> DiscoveryService:
    return cast("DiscoveryService", ctx.lifespan_context[LIFESPAN_KEYS.discovery_service])


def get_registry(ctx: Any = _CTX) -> SymbolRegistry:
    return cast("SymbolRegistry", ctx.lifespan_context[LIFESPAN_KEYS.registry])


def get_venue_states(ctx: Any = _CTX) -> dict[VenueId, VenueState]:
    return cast(
        "dict[VenueId, VenueState]",
        ctx.lifespan_context[LIFESPAN_KEYS.venue_states],
    )


def get_strategy_spec_repo(ctx: Any = _CTX) -> StrategySpecRepository:
    return cast(
        "StrategySpecRepository",
        ctx.lifespan_context[LIFESPAN_KEYS.strategy_spec_repo],
    )


def get_risk_policy_repo(ctx: Any = _CTX) -> RiskPolicyRepository:
    return cast(
        "RiskPolicyRepository",
        ctx.lifespan_context[LIFESPAN_KEYS.risk_policy_repo],
    )


def get_risk_engine(ctx: Any = _CTX) -> RiskEngine:
    return cast("RiskEngine", ctx.lifespan_context[LIFESPAN_KEYS.risk_engine])


def get_kill_switch(ctx: Any = _CTX) -> KillSwitch:
    return cast("KillSwitch", ctx.lifespan_context[LIFESPAN_KEYS.kill_switch])


def get_position_watcher(ctx: Any = _CTX) -> PositionWatcher:
    return cast(
        "PositionWatcher",
        ctx.lifespan_context[LIFESPAN_KEYS.position_watcher],
    )


def get_watch_registry(ctx: Any = _CTX) -> dict[str, WatchState]:
    return cast(
        "dict[str, WatchState]",
        ctx.lifespan_context[LIFESPAN_KEYS.watch_registry],
    )


def get_ws_provider(ctx: Any = _CTX) -> KucoinWsProvider:
    return cast(
        "KucoinWsProvider",
        ctx.lifespan_context[LIFESPAN_KEYS.ws_provider],
    )


def get_providers(ctx: Any = _CTX) -> dict[VenueId, Any]:
    return cast(
        "dict[VenueId, Any]",
        ctx.lifespan_context[LIFESPAN_KEYS.providers],
    )


def get_paper_ledger(ctx: Any = _CTX) -> PaperLedgerService:
    return cast(
        "PaperLedgerService",
        ctx.lifespan_context[LIFESPAN_KEYS.paper_ledger],
    )


def get_paper_repo(ctx: Any = _CTX) -> PaperTradeRepository:
    return cast(
        "PaperTradeRepository",
        ctx.lifespan_context[LIFESPAN_KEYS.paper_repo],
    )


def get_paper_bankroll_override(ctx: Any = _CTX) -> dict[str, Any]:
    return cast(
        "dict[str, Any]",
        ctx.lifespan_context[LIFESPAN_KEYS.paper_bankroll_override],
    )
