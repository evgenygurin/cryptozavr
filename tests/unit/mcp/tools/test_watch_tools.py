import asyncio
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


class _SilentWs:
    async def watch_ticker(self, native: str):
        await asyncio.Event().wait()
        yield  # unreachable

    async def close(self) -> None: ...


def _make_server(ws_provider) -> FastMCP:
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
    watcher = PositionWatcher(ws_provider=ws_provider, registry=registry)

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


@pytest.fixture
def mcp_server() -> FastMCP:
    return _make_server(_StubWs())


@pytest.fixture
def silent_mcp_server() -> FastMCP:
    return _make_server(_SilentWs())


_WATCH_ARGS = {
    "venue": "kucoin",
    "symbol": "BTC-USDT",
    "side": "long",
    "entry": "100",
    "stop": "95",
    "take": "110",
    "max_duration_sec": 3600,
}


async def test_watch_position_returns_watch_id(mcp_server: FastMCP) -> None:
    async with Client(mcp_server) as client:
        result = await client.call_tool("watch_position", _WATCH_ARGS)
        assert result.structured_content["watch_id"]
        assert result.structured_content["status"] in {"running", "stop_hit"}


async def test_check_watch_unknown_id_errors(mcp_server: FastMCP) -> None:
    async with Client(mcp_server) as client:
        with pytest.raises(Exception, match="not found"):
            await client.call_tool("check_watch", {"watch_id": "nope"})


async def test_stop_watch_terminates(mcp_server: FastMCP) -> None:
    async with Client(mcp_server) as client:
        started = await client.call_tool("watch_position", _WATCH_ARGS)
        watch_id = started.structured_content["watch_id"]
        stopped = await client.call_tool("stop_watch", {"watch_id": watch_id})
        assert stopped.structured_content["status"] in {"cancelled", "stop_hit"}


async def test_wait_for_event_returns_on_stop_hit(mcp_server: FastMCP) -> None:
    """Stub yields one tick at stop → stop_hit; wait_for_event returns quickly."""
    async with Client(mcp_server) as client:
        started = await client.call_tool("watch_position", _WATCH_ARGS)
        watch_id = started.structured_content["watch_id"]
        waited = await asyncio.wait_for(
            client.call_tool(
                "wait_for_event",
                {"watch_id": watch_id, "timeout_sec": 5},
            ),
            timeout=3.0,
        )
        events = waited.structured_content["events"]
        assert any(e["type"] == "stop_hit" for e in events)
        assert waited.structured_content["status"] == "stop_hit"


async def test_wait_for_event_times_out(silent_mcp_server: FastMCP) -> None:
    """Silent watcher never fires; wait_for_event must time out cleanly."""
    async with Client(silent_mcp_server) as client:
        started = await client.call_tool("watch_position", _WATCH_ARGS)
        watch_id = started.structured_content["watch_id"]
        waited = await asyncio.wait_for(
            client.call_tool(
                "wait_for_event",
                {"watch_id": watch_id, "timeout_sec": 1},
            ),
            timeout=3.0,
        )
        assert waited.structured_content["status"] == "running"
        assert waited.structured_content["events"] == []
        await client.call_tool("stop_watch", {"watch_id": watch_id})
