"""Production wiring for the MCP server.

Creates infrastructure (HTTP, rate limiters, symbol registry, venue states,
gateway, providers, realtime subscriber) and yields a single dict keyed
by `LIFESPAN_KEYS` for Depends(get_xxx_service) injection.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from supabase import AsyncClient, acreate_client

from cryptozavr.application.services.analytics_service import AnalyticsService
from cryptozavr.application.services.discovery_service import DiscoveryService
from cryptozavr.application.services.market_analyzer import MarketAnalyzer
from cryptozavr.application.services.ohlcv_service import OhlcvService
from cryptozavr.application.services.order_book_service import OrderBookService
from cryptozavr.application.services.symbol_resolver import SymbolResolver
from cryptozavr.application.services.ticker_service import TickerService
from cryptozavr.application.services.trades_service import TradesService
from cryptozavr.application.strategies.support_resistance import (
    SupportResistanceStrategy,
)
from cryptozavr.application.strategies.volatility import VolatilityRegimeStrategy
from cryptozavr.application.strategies.vwap import VwapStrategy
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.providers.factory import ProviderFactory
from cryptozavr.infrastructure.providers.http import HttpClientRegistry
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

    factory = ProviderFactory(
        http_registry=http_registry,
        rate_registry=rate_registry,
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
    }

    async def cleanup() -> None:
        _LOG.info("cryptozavr shutting down")
        try:
            await subscriber.close()
        except Exception as exc:
            _LOG.warning("realtime subscriber close failed: %s", exc)
        try:
            await http_registry.close_all()
        except Exception as exc:
            _LOG.warning("http registry close failed: %s", exc)
        try:
            await gateway.close()
        except Exception as exc:
            _LOG.warning("gateway close failed: %s", exc)
        try:
            await pg_pool.close()
        except Exception as exc:
            _LOG.warning("pg pool close failed: %s", exc)

    return state, cleanup
