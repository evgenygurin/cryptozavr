"""FastMCP server bootstrap with single echo tool.

M1 scope: echo only. Real tools arrive in M3.
"""

from __future__ import annotations

import logging
import sys
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from cryptozavr import __version__
from cryptozavr.mcp.settings import Settings

_LOGGER = logging.getLogger(__name__)


def build_server(settings: Settings) -> FastMCP[None]:
    """Build the FastMCP server instance.

    Args:
        settings: Runtime configuration loaded from env.

    Returns:
        Configured FastMCP instance ready for mcp.run().
    """
    mcp: FastMCP[None] = FastMCP(
        name="cryptozavr-research",
        version=__version__,
    )

    @mcp.tool(  # type: ignore[misc, unused-ignore]
        name="echo",
        description=(
            "Smoke-test tool. Returns the provided message with server version. "
            "Useful for verifying the plugin loads and dispatches tool calls correctly."
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

    _LOGGER.info(
        "cryptozavr-research built",
        extra={"mode": settings.mode.value, "version": __version__},
    )
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
    mcp.run()  # STDIO by default; transport auto-detected


if __name__ == "__main__":
    main()
