"""MCP-facing DTOs. Pydantic models for tool return types."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from cryptozavr.domain.market_data import Ticker


class TickerDTO(BaseModel):
    """Wire-format ticker for the get_ticker MCP tool."""

    model_config = ConfigDict(frozen=True)

    venue: str
    symbol: str
    last: Decimal
    bid: Decimal | None = None
    ask: Decimal | None = None
    volume_24h: Decimal | None = None
    observed_at_ms: int
    staleness: str
    confidence: str
    cache_hit: bool
    reason_codes: list[str]

    @classmethod
    def from_domain(cls, ticker: Ticker, reason_codes: list[str]) -> TickerDTO:
        return cls(
            venue=ticker.symbol.venue.value,
            symbol=ticker.symbol.native_symbol,
            last=ticker.last,
            bid=ticker.bid,
            ask=ticker.ask,
            volume_24h=ticker.volume_24h,
            observed_at_ms=ticker.observed_at.to_ms(),
            staleness=ticker.quality.staleness.name.lower(),
            confidence=ticker.quality.confidence.name.lower(),
            cache_hit=ticker.quality.cache_hit,
            reason_codes=list(reason_codes),
        )
