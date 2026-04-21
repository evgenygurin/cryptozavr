"""Test lifespan state keys + Depends accessors."""

from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import pytest
from fastmcp import Client, Context, FastMCP

from cryptozavr.mcp.lifespan_state import (
    LIFESPAN_KEYS,
    get_discovery_service,
    get_ohlcv_service,
    get_order_book_service,
    get_registry,
    get_subscriber,
    get_symbol_resolver,
    get_ticker_service,
    get_trades_service,
)


def test_lifespan_keys_are_strings_and_unique() -> None:
    names = [
        LIFESPAN_KEYS.ticker_service,
        LIFESPAN_KEYS.ohlcv_service,
        LIFESPAN_KEYS.order_book_service,
        LIFESPAN_KEYS.trades_service,
        LIFESPAN_KEYS.subscriber,
        LIFESPAN_KEYS.symbol_resolver,
        LIFESPAN_KEYS.discovery_service,
        LIFESPAN_KEYS.registry,
    ]
    assert all(isinstance(n, str) for n in names)
    assert len(set(names)) == len(names)


def test_accessor_callables_exist() -> None:
    assert callable(get_ticker_service)
    assert callable(get_ohlcv_service)
    assert callable(get_order_book_service)
    assert callable(get_trades_service)
    assert callable(get_subscriber)
    assert callable(get_symbol_resolver)
    assert callable(get_discovery_service)
    assert callable(get_registry)


@pytest.mark.asyncio
async def test_accessor_pulls_value_from_lifespan_dict() -> None:
    ticker_stub = MagicMock(name="ticker_service_stub")
    ticker_stub.sentinel = "ticker-ok"

    @asynccontextmanager
    async def lifespan(_server):
        yield {LIFESPAN_KEYS.ticker_service: ticker_stub}

    mcp = FastMCP(name="t", version="0", lifespan=lifespan)

    @mcp.tool
    async def probe(ctx: Context) -> dict[str, str]:
        svc = ctx.lifespan_context[LIFESPAN_KEYS.ticker_service]
        return {"sentinel": str(svc.sentinel)}

    async with Client(mcp) as client:
        result = await client.call_tool("probe", {})
    payload = result.structured_content or {}
    assert payload.get("sentinel") == "ticker-ok"
