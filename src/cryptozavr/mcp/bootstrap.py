"""Production wiring for the MCP server.

Creates infrastructure (HTTP, rate limiters, symbol registry, venue states,
gateway, providers, realtime subscriber, observability) and yields a single
dict keyed by `LIFESPAN_KEYS` for Depends(get_xxx_service) injection.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from supabase import AsyncClient, acreate_client

from cryptozavr.application.risk.engine import RiskEngine, default_handler_chain
from cryptozavr.application.risk.kill_switch import KillSwitch
from cryptozavr.application.services.analytics_service import AnalyticsService
from cryptozavr.application.services.cache_invalidator import CacheInvalidator
from cryptozavr.application.services.discovery_service import DiscoveryService
from cryptozavr.application.services.health_monitor import (
    HealthMonitor,
    HealthProbe,
)
from cryptozavr.application.services.market_analyzer import MarketAnalyzer
from cryptozavr.application.services.ohlcv_service import OhlcvService
from cryptozavr.application.services.order_book_service import OrderBookService
from cryptozavr.application.services.paper_ledger_service import PaperLedgerService
from cryptozavr.application.services.position_watcher import PositionWatcher
from cryptozavr.application.services.symbol_resolver import SymbolResolver
from cryptozavr.application.services.ticker_service import TickerService
from cryptozavr.application.services.ticker_sync_worker import TickerSyncWorker
from cryptozavr.application.services.trades_service import TradesService
from cryptozavr.application.strategies.support_resistance import (
    SupportResistanceStrategy,
)
from cryptozavr.application.strategies.volatility import VolatilityRegimeStrategy
from cryptozavr.application.strategies.vwap import VwapStrategy
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.domain.watch import WatchState
from cryptozavr.infrastructure.observability.metrics import MetricsRegistry
from cryptozavr.infrastructure.persistence.paper_trade_repo import PaperTradeRepository
from cryptozavr.infrastructure.persistence.risk_policy_repo import (
    RiskPolicyRepository,
)
from cryptozavr.infrastructure.persistence.strategy_spec_repo import (
    StrategySpecRepository,
)
from cryptozavr.infrastructure.providers.factory import ProviderFactory
from cryptozavr.infrastructure.providers.http import HttpClientRegistry
from cryptozavr.infrastructure.providers.kucoin_ws import KucoinWsProvider
from cryptozavr.infrastructure.providers.rate_limiters import (
    RateLimiterRegistry,
)
from cryptozavr.infrastructure.providers.state.venue_state import VenueState
from cryptozavr.infrastructure.supabase.gateway import SupabaseGateway
from cryptozavr.infrastructure.supabase.pg_pool import (
    PgPoolConfig,
    create_pool,
)
from cryptozavr.infrastructure.supabase.realtime import RealtimeSubscriber
from cryptozavr.mcp.lifespan_state import LIFESPAN_KEYS
from cryptozavr.mcp.settings import Settings

_LOG = logging.getLogger(__name__)


async def _build_background_services(
    *,
    providers: dict[VenueId, Any],
    venue_states: dict[VenueId, VenueState],
    metrics_registry: MetricsRegistry,
    ticker_service: TickerService,
    subscriber: RealtimeSubscriber,
) -> tuple[HealthMonitor, TickerSyncWorker, CacheInvalidator]:
    probes: dict[VenueId, HealthProbe] = {
        venue_id: providers[venue_id].load_markets for venue_id in providers
    }
    health_monitor = HealthMonitor(
        probes=probes,
        states=venue_states,
        metrics=metrics_registry,
    )
    ticker_sync_worker = TickerSyncWorker(
        ticker_service=ticker_service,
        subscriber=subscriber,
    )
    cache_invalidator = CacheInvalidator(
        subscriber=subscriber,
        providers=providers,
    )
    for starter, label in (
        (health_monitor.start, "health monitor"),
        (ticker_sync_worker.start, "ticker sync worker"),
        (cache_invalidator.start, "cache invalidator"),
    ):
        try:
            await starter()
        except Exception:
            _LOG.exception("%s failed to start", label)
    return health_monitor, ticker_sync_worker, cache_invalidator


async def build_production_service(
    settings: Settings,
) -> tuple[dict[str, Any], Callable[[], Awaitable[None]]]:
    """Build production state + cleanup coroutine.

    Returns a plain dict keyed by LIFESPAN_KEYS so tools can
    Depends(get_xxx_service) into it. The caller (server.py) yields
    this dict from its @asynccontextmanager lifespan.
    """
    http_registry = HttpClientRegistry()

    rate_registry = RateLimiterRegistry()
    rate_registry.register("kucoin", rate_per_sec=30.0, capacity=30)
    rate_registry.register("coingecko", rate_per_sec=0.5, capacity=30)

    metrics_registry = MetricsRegistry()

    registry = SymbolRegistry()
    registry.get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )
    registry.get(
        VenueId.KUCOIN,
        "ETH",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="ETH-USDT",
    )
    venue_states = {
        VenueId.KUCOIN: VenueState(VenueId.KUCOIN),
        VenueId.COINGECKO: VenueState(VenueId.COINGECKO),
    }

    pg_pool = await create_pool(PgPoolConfig(dsn=settings.supabase_db_url))
    gateway = SupabaseGateway(pg_pool, registry)
    strategy_spec_repo = StrategySpecRepository(pool=pg_pool)
    risk_policy_repo = RiskPolicyRepository(pool=pg_pool)
    kill_switch = KillSwitch()
    risk_engine = RiskEngine(handlers=default_handler_chain(), kill_switch=kill_switch)

    factory = ProviderFactory(
        http_registry=http_registry,
        rate_registry=rate_registry,
        metrics_registry=metrics_registry,
    )
    providers = {
        VenueId.KUCOIN: factory.create_kucoin(
            state=venue_states[VenueId.KUCOIN],
        ),
        VenueId.COINGECKO: await factory.create_coingecko(
            state=venue_states[VenueId.COINGECKO],
        ),
    }

    ticker_service = TickerService(
        registry=registry,
        venue_states=venue_states,
        providers=providers,
        gateway=gateway,
    )
    ohlcv_service = OhlcvService(
        registry=registry,
        venue_states=venue_states,
        providers=providers,
        gateway=gateway,
    )
    order_book_service = OrderBookService(
        registry=registry,
        venue_states=venue_states,
        providers=providers,
        gateway=gateway,
    )
    trades_service = TradesService(
        registry=registry,
        venue_states=venue_states,
        providers=providers,
        gateway=gateway,
    )

    analyzer = MarketAnalyzer(
        strategies={
            "vwap": VwapStrategy(),
            "support_resistance": SupportResistanceStrategy(),
            "volatility_regime": VolatilityRegimeStrategy(),
        },
    )
    analytics_service = AnalyticsService(
        ohlcv_service=ohlcv_service,
        analyzer=analyzer,
    )

    supabase_client: AsyncClient = await acreate_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )
    subscriber = RealtimeSubscriber(client=supabase_client)

    symbol_resolver = SymbolResolver(registry)
    discovery_service = DiscoveryService(
        coingecko=providers[VenueId.COINGECKO],
    )

    ws_provider = KucoinWsProvider()
    watch_registry: dict[str, WatchState] = {}
    position_watcher = PositionWatcher(
        ws_provider=ws_provider,
        registry=watch_registry,
    )

    paper_repo = PaperTradeRepository(pool=pg_pool)
    paper_ledger = PaperLedgerService(
        repository=paper_repo,
        watcher=position_watcher,
        resolver=symbol_resolver,
    )
    paper_bankroll_override: dict[str, Any] = {"value": None}

    (
        health_monitor,
        ticker_sync_worker,
        cache_invalidator,
    ) = await _build_background_services(
        providers=providers,
        venue_states=venue_states,
        metrics_registry=metrics_registry,
        ticker_service=ticker_service,
        subscriber=subscriber,
    )

    state: dict[str, Any] = {
        LIFESPAN_KEYS.ticker_service: ticker_service,
        LIFESPAN_KEYS.ohlcv_service: ohlcv_service,
        LIFESPAN_KEYS.order_book_service: order_book_service,
        LIFESPAN_KEYS.trades_service: trades_service,
        LIFESPAN_KEYS.analytics_service: analytics_service,
        LIFESPAN_KEYS.subscriber: subscriber,
        LIFESPAN_KEYS.registry: registry,
        LIFESPAN_KEYS.symbol_resolver: symbol_resolver,
        LIFESPAN_KEYS.discovery_service: discovery_service,
        LIFESPAN_KEYS.venue_states: venue_states,
        LIFESPAN_KEYS.metrics_registry: metrics_registry,
        LIFESPAN_KEYS.health_monitor: health_monitor,
        LIFESPAN_KEYS.ticker_sync_worker: ticker_sync_worker,
        LIFESPAN_KEYS.cache_invalidator: cache_invalidator,
        LIFESPAN_KEYS.strategy_spec_repo: strategy_spec_repo,
        LIFESPAN_KEYS.risk_policy_repo: risk_policy_repo,
        LIFESPAN_KEYS.risk_engine: risk_engine,
        LIFESPAN_KEYS.kill_switch: kill_switch,
        LIFESPAN_KEYS.ws_provider: ws_provider,
        LIFESPAN_KEYS.position_watcher: position_watcher,
        LIFESPAN_KEYS.watch_registry: watch_registry,
        LIFESPAN_KEYS.paper_repo: paper_repo,
        LIFESPAN_KEYS.paper_ledger: paper_ledger,
        LIFESPAN_KEYS.paper_bankroll_override: paper_bankroll_override,
    }

    try:
        await paper_ledger.resume_open_watches()
    except Exception:
        _LOG.warning("paper_ledger resume_open_watches failed", exc_info=True)

    async def cleanup() -> None:
        await _shutdown(
            watch_registry=watch_registry,
            ws_provider=ws_provider,
            cache_invalidator=cache_invalidator,
            ticker_sync_worker=ticker_sync_worker,
            health_monitor=health_monitor,
            providers=providers,
            subscriber=subscriber,
            http_registry=http_registry,
            gateway=gateway,
            pg_pool=pg_pool,
        )

    return state, cleanup


async def _shutdown(
    *,
    watch_registry: dict[str, WatchState],
    ws_provider: KucoinWsProvider,
    cache_invalidator: CacheInvalidator,
    ticker_sync_worker: TickerSyncWorker,
    health_monitor: HealthMonitor,
    providers: dict[VenueId, Any],
    subscriber: RealtimeSubscriber,
    http_registry: HttpClientRegistry,
    gateway: SupabaseGateway,
    pg_pool: Any,
) -> None:
    _LOG.info("cryptozavr shutting down")
    # Cancel active watches first so their per-watch tasks don't fight WS close.
    for _state in watch_registry.values():
        _task = _state._task
        if _task is not None and not _task.done():
            _task.cancel()
    if watch_registry:
        await asyncio.gather(
            *(s._task for s in watch_registry.values() if s._task is not None),
            return_exceptions=True,
        )
    try:
        await ws_provider.close()
    except Exception:
        _LOG.exception("ws_provider close failed")
    for stopper, label in (
        (cache_invalidator.stop, "cache invalidator"),
        (ticker_sync_worker.stop, "ticker sync worker"),
        (health_monitor.stop, "health monitor"),
    ):
        try:
            await stopper()
        except Exception:
            _LOG.exception("%s stop failed", label)
    for venue_id, provider in providers.items():
        try:
            await provider.close()
        except Exception:
            _LOG.exception("provider %s close failed", venue_id)
    for closer, label in (
        (subscriber.close, "realtime subscriber"),
        (http_registry.close_all, "http registry"),
        (gateway.close, "gateway"),
        (pg_pool.close, "pg pool"),
    ):
        try:
            await closer()
        except Exception:
            _LOG.exception("%s close failed", label)
