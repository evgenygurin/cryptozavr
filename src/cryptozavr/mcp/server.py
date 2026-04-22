"""FastMCP server bootstrap: echo + 4 market-data tools.

Uses FastMCP v3 lifespan (dict-yield) + mask_error_details for
production safety.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from cryptozavr import __version__
from cryptozavr.mcp.bootstrap import build_production_service
from cryptozavr.mcp.prompts.research import register_prompts
from cryptozavr.mcp.resources.catalogs import register_resources
from cryptozavr.mcp.settings import Settings
from cryptozavr.mcp.tools.analytics import register_analytics_tools
from cryptozavr.mcp.tools.discovery import register_resolve_symbol_tool
from cryptozavr.mcp.tools.ohlcv import register_ohlcv_tool
from cryptozavr.mcp.tools.order_book import register_order_book_tool
from cryptozavr.mcp.tools.ticker import register_ticker_tool
from cryptozavr.mcp.tools.trades import register_trades_tool

_LOGGER = logging.getLogger(__name__)


def _register_echo(mcp: FastMCP) -> None:
    @mcp.tool(
        name="echo",
        description=(
            "Smoke-test tool. Returns the provided message with server "
            "version. Useful for verifying plugin load and dispatch."
        ),
        tags={"smoke", "mvp", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    def echo(
        message: Annotated[str, Field(description="Any string to echo back.")],
    ) -> dict[str, str]:
        """Echo the input message with server version metadata."""
        return {"message": message, "version": __version__}


def build_server(settings: Settings) -> FastMCP:
    """Build the FastMCP server with dict-lifespan + mask_error_details."""

    @asynccontextmanager
    async def lifespan(
        _server: FastMCP,
    ) -> AsyncIterator[dict[str, Any]]:
        state, cleanup = await build_production_service(settings)
        _LOGGER.info(
            "cryptozavr-research started",
            extra={"mode": settings.mode.value, "version": __version__},
        )
        try:
            yield state
        finally:
            await cleanup()

    mcp = FastMCP(
        name="cryptozavr-research",
        version=__version__,
        lifespan=lifespan,
        mask_error_details=True,
    )
    _register_echo(mcp)
    register_ticker_tool(mcp)
    register_ohlcv_tool(mcp)
    register_order_book_tool(mcp)
    register_trades_tool(mcp)
    register_resolve_symbol_tool(mcp)
    register_analytics_tools(mcp)
    register_prompts(mcp)
    register_resources(mcp)
    return mcp


def main() -> None:
    """Entrypoint for `python -m cryptozavr.mcp.server` and console_scripts."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    settings = Settings()  # type: ignore[call-arg]
    mcp = build_server(settings)
    mcp.run()


if __name__ == "__main__":
    main()
