"""Test cryptozavr://venue_health resource."""

import json
from contextlib import asynccontextmanager

import pytest
from fastmcp import Client, FastMCP

from cryptozavr.domain.venues import VenueId, VenueStateKind
from cryptozavr.infrastructure.providers.state.venue_state import VenueState
from cryptozavr.mcp.lifespan_state import LIFESPAN_KEYS
from cryptozavr.mcp.resources.venue_health import register_venue_health_resource


def _build_server(venue_states: dict[VenueId, VenueState]) -> FastMCP:
    @asynccontextmanager
    async def lifespan(_server):
        yield {LIFESPAN_KEYS.venue_states: venue_states}

    mcp = FastMCP(name="t", version="0", lifespan=lifespan)
    register_venue_health_resource(mcp)
    return mcp


@pytest.mark.asyncio
async def test_empty_venue_states_returns_empty_list() -> None:
    mcp = _build_server({})
    async with Client(mcp) as client:
        result = await client.read_resource("cryptozavr://venue_health")
    payload = json.loads(result[0].text)
    assert payload == {"venues": []}


@pytest.mark.asyncio
async def test_healthy_venue_reports_healthy() -> None:
    states = {VenueId.KUCOIN: VenueState(VenueId.KUCOIN)}
    states[VenueId.KUCOIN].mark_probe_performed(1_700_000_000_000)
    mcp = _build_server(states)
    async with Client(mcp) as client:
        result = await client.read_resource("cryptozavr://venue_health")
    payload = json.loads(result[0].text)
    assert payload["venues"] == [
        {
            "venue": "kucoin",
            "state": "healthy",
            "last_checked_ms": 1_700_000_000_000,
        }
    ]


@pytest.mark.asyncio
async def test_rate_limited_is_reported_as_degraded() -> None:
    state = VenueState(VenueId.KUCOIN, kind=VenueStateKind.DEGRADED)
    mcp = _build_server({VenueId.KUCOIN: state})
    async with Client(mcp) as client:
        result = await client.read_resource("cryptozavr://venue_health")
    payload = json.loads(result[0].text)
    assert payload["venues"][0]["state"] == "degraded"


@pytest.mark.asyncio
async def test_down_state_is_reported_as_down() -> None:
    state = VenueState(VenueId.KUCOIN, kind=VenueStateKind.DOWN)
    mcp = _build_server({VenueId.KUCOIN: state})
    async with Client(mcp) as client:
        result = await client.read_resource("cryptozavr://venue_health")
    payload = json.loads(result[0].text)
    assert payload["venues"][0]["state"] == "down"


@pytest.mark.asyncio
async def test_last_checked_ms_is_null_when_never_probed() -> None:
    states = {
        VenueId.KUCOIN: VenueState(VenueId.KUCOIN),
        VenueId.COINGECKO: VenueState(VenueId.COINGECKO),
    }
    mcp = _build_server(states)
    async with Client(mcp) as client:
        result = await client.read_resource("cryptozavr://venue_health")
    payload = json.loads(result[0].text)
    by_venue = {v["venue"]: v for v in payload["venues"]}
    assert by_venue["kucoin"]["last_checked_ms"] is None
    assert by_venue["coingecko"]["last_checked_ms"] is None
