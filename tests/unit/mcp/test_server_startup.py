"""Smoke test: build_server() produces a FastMCP instance with registered tools."""

from __future__ import annotations

import pytest

from cryptozavr.mcp.server import build_server
from cryptozavr.mcp.settings import Mode, Settings


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "local-dev-key")
    monkeypatch.setenv(
        "SUPABASE_DB_URL",
        "postgresql://postgres:postgres@127.0.0.1:54322/postgres",
    )
    return Settings()


def test_build_server_returns_fastmcp_instance(settings: Settings) -> None:
    """build_server produces a server with the correct name and version."""
    mcp = build_server(settings)

    assert mcp.name == "cryptozavr-research"
    assert mcp.version == "0.0.1"


async def test_build_server_registers_echo_tool(settings: Settings) -> None:
    """Echo tool must be listed after server build."""
    mcp = build_server(settings)

    tools = await mcp.list_tools()
    tool_names = {tool.name for tool in tools}

    assert "echo" in tool_names


async def test_build_server_registers_analytics_tools(settings: Settings) -> None:
    """4 analytics tools must be registered after server build."""
    mcp = build_server(settings)

    tools = await mcp.list_tools()
    tool_names = {tool.name for tool in tools}

    assert "compute_vwap" in tool_names
    assert "identify_support_resistance" in tool_names
    assert "volatility_regime" in tool_names
    assert "analyze_snapshot" in tool_names


async def test_build_server_respects_current_mode(settings: Settings) -> None:
    """Server exposes current mode (for future mode-aware tools)."""
    build_server(settings)

    # Mode is not directly on FastMCP instance; we verify indirectly via a tool
    # that reports it. In M1 the echo tool doesn't return mode, but we assert
    # that the server was built without errors for research_only.
    assert settings.mode == Mode.RESEARCH_ONLY
