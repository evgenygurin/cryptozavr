"""Production wiring for the MCP server.

Creates infrastructure (HTTP, rate limiters, symbol registry, venue states,
gateway, providers), assembles a TickerService, and returns a cleanup
coroutine the caller must await on shutdown.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from supabase import AsyncClient, acreate_client

from cryptozavr.application.services.ohlcv_service import OhlcvService
from cryptozavr.application.services.order_book_service import OrderBookService
from cryptozavr.application.services.ticker_service import TickerService
from cryptozavr.application.services.trades_service import TradesService
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
from cryptozavr.mcp.settings import Settings

_LOG = logging.getLogger(__name__)


@dataclass(slots=True)
class AppState:
    """Lifespan-scoped application state exposed to tools."""

    ticker_service: TickerService
    ohlcv_service: OhlcvService
    order_book_service: OrderBookService
    trades_service: TradesService
    subscriber: RealtimeSubscriber


async def build_production_service(
    settings: Settings,
) -> tuple[
    TickerService,
    OhlcvService,
    OrderBookService,
    TradesService,
    RealtimeSubscriber,
    Callable[[], Awaitable[None]],
]:
    """Build production TickerService + OhlcvService and a cleanup coroutine."""
    http_registry = HttpClientRegistry()

    rate_registry = RateLimiterRegistry()
    rate_registry.register("kucoin", rate_per_sec=30.0, capacity=30)
    rate_registry.register("coingecko", rate_per_sec=0.5, capacity=30)

    registry = SymbolRegistry()
    # MVP seed — extend to DB-driven in M2.5+.
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

    supabase_client: AsyncClient = await acreate_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )
    subscriber = RealtimeSubscriber(client=supabase_client)

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

    return (
        ticker_service,
        ohlcv_service,
        order_book_service,
        trades_service,
        subscriber,
        cleanup,
    )
