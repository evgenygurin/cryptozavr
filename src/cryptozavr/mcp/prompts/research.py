"""research_symbol + risk_check prompts."""

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field


def register_prompts(mcp: FastMCP) -> None:
    """Attach research + risk prompts to the given FastMCP instance."""

    @mcp.prompt(
        name="research_symbol",
        description=("Full 4-tool market research collage for a symbol on a venue."),
        tags={"market", "research"},
    )
    def research_symbol(
        venue: Annotated[
            str,
            Field(description="Venue id: kucoin, coingecko."),
        ],
        symbol: Annotated[
            str,
            Field(description="Native symbol, e.g. BTC-USDT."),
        ],
    ) -> str:
        return (
            f"Research {symbol} on venue {venue}. Call these 4 tools in "
            f"parallel: `get_ticker`, `get_ohlcv(timeframe='1h', limit=24)`, "
            f"`get_order_book(depth=20)`, `get_trades(limit=50)`. "
            f"Present the result as: Price → Trend → Liquidity → Flow → "
            f"Provenance. Rails: data-not-advice. Surface reason_codes "
            f"and any non-fresh staleness warnings from tool calls."
        )

    @mcp.prompt(
        name="risk_check",
        description=(
            "Risk-first pre-decision check for a symbol. "
            "Focuses on data quality, not price prediction."
        ),
        tags={"market", "risk"},
    )
    def risk_check(
        venue: Annotated[
            str,
            Field(description="Venue id."),
        ],
        symbol: Annotated[
            str,
            Field(description="Native symbol."),
        ],
    ) -> str:
        return (
            f"Run a risk-first quality check on {symbol} at venue {venue}.\n\n"
            f"Steps:\n"
            f"1. Call `get_ticker` with force_refresh=true — record "
            f"staleness, cache_hit, reason_codes.\n"
            f"2. If staleness != 'fresh' or confidence != 'high' — stop and "
            f"flag: data quality too low for decisions.\n"
            f"3. Call `get_order_book(depth=20)` — compute spread_bps. "
            f"If spread_bps > 50 bps, flag: illiquid.\n"
            f"4. Call `get_trades(limit=50)` — check buy/sell count ratio. "
            f"Extreme imbalance (>80/20) → flag: one-sided tape.\n\n"
            f"Report: PASS | DEGRADED | FAIL with the specific reason_codes "
            f"that triggered each flag. No buy/sell recommendations."
        )
