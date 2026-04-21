"""FastMCP server bootstrap: echo + get_ticker + get_ohlcv.

Uses FastMCP v3 lifespan to own TickerService and OhlcvService lifecycle.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from cryptozavr import __version__
from cryptozavr.mcp.bootstrap import AppState, build_production_service
from cryptozavr.mcp.settings import Settings
from cryptozavr.mcp.tools.ohlcv import register_ohlcv_tool
from cryptozavr.mcp.tools.ticker import register_ticker_tool

_LOGGER = logging.getLogger(__name__)


def _register_echo(mcp: FastMCP[AppState]) -> None:
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


def build_server(settings: Settings) -> FastMCP[AppState]:
    """Build the FastMCP server with production lifespan."""

    @asynccontextmanager
    async def lifespan(
        _server: FastMCP[AppState],
    ) -> AsyncIterator[AppState]:
        ticker_service, ohlcv_service, cleanup = await build_production_service(settings)
        _LOGGER.info(
            "cryptozavr-research started",
            extra={"mode": settings.mode.value, "version": __version__},
        )
        try:
            yield AppState(
                ticker_service=ticker_service,
                ohlcv_service=ohlcv_service,
            )
        finally:
            await cleanup()

    mcp: FastMCP[AppState] = FastMCP(
        name="cryptozavr-research",
        version=__version__,
        lifespan=lifespan,
    )
    _register_echo(mcp)
    register_ticker_tool(mcp)
    register_ohlcv_tool(mcp)
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
    mcp.run()  # STDIO default


if __name__ == "__main__":
    main()
