"""Tests for the validate_strategy MCP tool.

Uses the same Client(mcp).call_tool(...) pattern as test_catalog_tools.
validate_strategy is pure (no DI dependencies) so a trivial no-op lifespan
is sufficient.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from copy import deepcopy

import pytest
from fastmcp import Client, FastMCP

from cryptozavr.mcp.tools.validate_strategy import register_validate_strategy_tool


def _build_server() -> FastMCP:
    @asynccontextmanager
    async def lifespan(_server):  # type: ignore[no-untyped-def]
        yield {}

    mcp = FastMCP(name="t", version="0", lifespan=lifespan)
    register_validate_strategy_tool(mcp)
    return mcp


def _structured(result) -> dict:  # type: ignore[no-untyped-def]
    sc = getattr(result, "structured_content", None)
    if sc is not None:
        return sc
    return json.loads(result.content[0].text)


def _valid_payload() -> dict:
    return {
        "name": "sma-cross",
        "description": "fast-over-slow SMA cross",
        "venue": "kucoin",
        "symbol": {
            "venue": "kucoin",
            "base": "BTC",
            "quote": "USDT",
            "market_type": "spot",
            "native_symbol": "BTC-USDT",
        },
        "timeframe": "1h",
        "entry": {
            "side": "long",
            "conditions": [
                {
                    "lhs": {"kind": "sma", "period": 10, "source": "close"},
                    "op": "gt",
                    "rhs": {"kind": "sma", "period": 50, "source": "close"},
                },
            ],
        },
        "exit": {
            "conditions": [],
            "take_profit_pct": "0.05",
            "stop_loss_pct": "0.02",
        },
        "size_pct": "0.25",
        "version": 1,
    }


@pytest.mark.asyncio
async def test_valid_payload_returns_valid_true() -> None:
    mcp = _build_server()
    async with Client(mcp) as client:
        result = await client.call_tool("validate_strategy", {"spec": _valid_payload()})
    payload = _structured(result)
    assert payload["valid"] is True
    assert payload["issues"] == []


@pytest.mark.asyncio
async def test_missing_required_field_returns_issue() -> None:
    mcp = _build_server()
    bad = _valid_payload()
    del bad["name"]
    async with Client(mcp) as client:
        result = await client.call_tool("validate_strategy", {"spec": bad})
    payload = _structured(result)
    assert payload["valid"] is False
    assert any("name" in issue["location"] for issue in payload["issues"])


@pytest.mark.asyncio
async def test_unknown_venue_returns_issue() -> None:
    mcp = _build_server()
    bad = _valid_payload()
    bad["venue"] = "fakevenue"
    bad["symbol"]["venue"] = "fakevenue"
    async with Client(mcp) as client:
        result = await client.call_tool("validate_strategy", {"spec": bad})
    payload = _structured(result)
    assert payload["valid"] is False
    assert payload["issues"], "expected at least one issue for unknown venue"


@pytest.mark.asyncio
async def test_size_pct_above_one_returns_issue() -> None:
    mcp = _build_server()
    bad = _valid_payload()
    bad["size_pct"] = "1.5"
    async with Client(mcp) as client:
        result = await client.call_tool("validate_strategy", {"spec": bad})
    payload = _structured(result)
    assert payload["valid"] is False
    assert any("size_pct" in issue["location"] for issue in payload["issues"])


@pytest.mark.asyncio
async def test_lowercase_base_returns_value_error_issue() -> None:
    """Symbol.__post_init__ raises domain ValidationError for non-uppercase base;
    validate_strategy should surface this as a value_error issue, not crash.
    """
    mcp = _build_server()
    bad = _valid_payload()
    bad["symbol"]["base"] = "btc"
    async with Client(mcp) as client:
        result = await client.call_tool("validate_strategy", {"spec": bad})
    payload = _structured(result)
    assert payload["valid"] is False
    assert payload["issues"]
    assert any(issue["type"] == "value_error" for issue in payload["issues"])


@pytest.mark.asyncio
async def test_venue_mismatch_returns_issue() -> None:
    mcp = _build_server()
    bad = _valid_payload()
    bad["venue"] = "coingecko"  # symbol.venue stays kucoin
    async with Client(mcp) as client:
        result = await client.call_tool("validate_strategy", {"spec": bad})
    payload = _structured(result)
    assert payload["valid"] is False


@pytest.mark.asyncio
async def test_response_has_structured_content() -> None:
    mcp = _build_server()
    async with Client(mcp) as client:
        result = await client.call_tool("validate_strategy", {"spec": _valid_payload()})
    # Either structured_content is populated directly, or text content parses
    # as JSON with the expected keys.
    sc = getattr(result, "structured_content", None)
    if sc is not None:
        assert "valid" in sc
        assert "issues" in sc
    else:
        parsed = json.loads(result.content[0].text)
        assert "valid" in parsed
        assert "issues" in parsed


@pytest.mark.asyncio
async def test_deep_nested_bad_type_returns_issue() -> None:
    """Ensure error location is preserved for nested fields."""
    mcp = _build_server()
    bad = deepcopy(_valid_payload())
    bad["entry"]["conditions"][0]["lhs"]["period"] = 0  # gt=0 fails
    async with Client(mcp) as client:
        result = await client.call_tool("validate_strategy", {"spec": bad})
    payload = _structured(result)
    assert payload["valid"] is False
    # One of the issues should mention period somewhere in its location path.
    assert any("period" in issue["location"] for issue in payload["issues"])
