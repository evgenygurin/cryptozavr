"""In-memory Client tests for cryptozavr prompts."""

import pytest
from fastmcp import Client, FastMCP

from cryptozavr.mcp.prompts.research import register_prompts


@pytest.mark.asyncio
async def test_research_symbol_prompt_lists_tools_and_rails() -> None:
    mcp = FastMCP(name="t", version="0")
    register_prompts(mcp)
    async with Client(mcp) as client:
        prompts = await client.list_prompts()
        names = {p.name for p in prompts}
        assert "research_symbol" in names
        result = await client.get_prompt(
            "research_symbol",
            {"venue": "kucoin", "symbol": "BTC-USDT"},
        )
    text = "".join(str(m.content) for m in result.messages)
    assert "kucoin" in text.lower()
    assert "BTC-USDT" in text
    assert "get_ticker" in text
    assert "get_ohlcv" in text


@pytest.mark.asyncio
async def test_risk_check_prompt_references_staleness_and_reason_codes() -> None:
    mcp = FastMCP(name="t", version="0")
    register_prompts(mcp)
    async with Client(mcp) as client:
        result = await client.get_prompt(
            "risk_check",
            {"venue": "kucoin", "symbol": "BTC-USDT"},
        )
    text = "".join(str(m.content) for m in result.messages)
    assert "staleness" in text.lower()
    assert "reason_codes" in text.lower()


@pytest.mark.asyncio
async def test_both_prompts_registered() -> None:
    mcp = FastMCP(name="t", version="0")
    register_prompts(mcp)
    async with Client(mcp) as client:
        prompts = await client.list_prompts()
    names = {p.name for p in prompts}
    assert names == {"research_symbol", "risk_check"}
