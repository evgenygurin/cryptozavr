"""Direct server call pattern (FastMCP v3 test style — see v3-notes/provider-test-pattern.md)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cryptozavr import __version__
from cryptozavr.mcp.server import build_server
from cryptozavr.mcp.settings import Settings


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "local-dev-key")
    monkeypatch.setenv(
        "SUPABASE_DB_URL",
        "postgresql://postgres:postgres@127.0.0.1:54322/postgres",
    )
    return Settings()


async def test_echo_tool_returns_the_same_message(settings: Settings) -> None:
    """echo(message) -> {"message": message, "version": __version__}."""
    mcp = build_server(settings)

    result = await mcp.call_tool("echo", {"message": "hello cryptozavr"})

    assert result.structured_content == {
        "message": "hello cryptozavr",
        "version": __version__,
    }


async def test_echo_tool_handles_empty_string(settings: Settings) -> None:
    """Empty message is allowed and echoed back."""
    mcp = build_server(settings)

    result = await mcp.call_tool("echo", {"message": ""})

    assert result.structured_content == {"message": "", "version": __version__}


async def test_echo_tool_rejects_missing_message(settings: Settings) -> None:
    """Missing required argument raises ValidationError."""
    mcp = build_server(settings)

    with pytest.raises(ValidationError):
        await mcp.call_tool("echo", {})
