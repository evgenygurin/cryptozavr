from contextlib import asynccontextmanager
from decimal import Decimal

import pytest
from fastmcp import Client, FastMCP

from cryptozavr.application.services.position_watcher import PositionWatcher
from cryptozavr.application.services.symbol_resolver import SymbolResolver
from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.mcp.lifespan_state import LIFESPAN_KEYS
from cryptozavr.mcp.tools.watch import register_watch_tools


class _StubWs:
    async def watch_ticker(self, native: str):
        yield Decimal("95"), 2_000  # single tick at stop → stop_hit

    async def close(self) -> None: ...


@pytest.fixture
def mcp_server():
    reg = SymbolRegistry()
    reg.get(
        VenueId.KUCOIN,
        "BTC",
        "USDT",
        market_type=MarketType.SPOT,
        native_symbol="BTC-USDT",
    )
    resolver = SymbolResolver(reg)
    registry: dict = {}
    watcher = PositionWatcher(ws_provider=_StubWs(), registry=registry)

    @asynccontextmanager
    async def lifespan(_server):
        yield {
            LIFESPAN_KEYS.symbol_resolver: resolver,
            LIFESPAN_KEYS.position_watcher: watcher,
            LIFESPAN_KEYS.watch_registry: registry,
        }

    mcp = FastMCP("test", lifespan=lifespan)
    register_watch_tools(mcp)
    return mcp


async def test_watch_position_returns_watch_id(mcp_server) -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "watch_position",
            {
                "venue": "kucoin",
                "symbol": "BTC-USDT",
                "side": "long",
                "entry": "100",
                "stop": "95",
                "take": "110",
                "max_duration_sec": 3600,
            },
        )
        assert result.structured_content["watch_id"]
        assert result.structured_content["status"] in {"running", "stop_hit"}


async def test_check_watch_unknown_id_errors(mcp_server) -> None:
    async with Client(mcp_server) as client:
        with pytest.raises(Exception, match="not found"):
            await client.call_tool("check_watch", {"watch_id": "nope"})


async def test_stop_watch_terminates(mcp_server) -> None:
    async with Client(mcp_server) as client:
        started = await client.call_tool(
            "watch_position",
            {
                "venue": "kucoin",
                "symbol": "BTC-USDT",
                "side": "long",
                "entry": "100",
                "stop": "95",
                "take": "110",
                "max_duration_sec": 3600,
            },
        )
        watch_id = started.structured_content["watch_id"]
        stopped = await client.call_tool("stop_watch", {"watch_id": watch_id})
        assert stopped.structured_content["status"] in {"cancelled", "stop_hit"}
