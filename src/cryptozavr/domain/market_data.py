"""Market data entities: Ticker, OHLCV, OrderBook, Trades, MarketSnapshot."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from cryptozavr.domain.quality import DataQuality
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Instant, Percentage


class TradeSide(StrEnum):
    BUY = "buy"
    SELL = "sell"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Ticker:
    """Last price + 24h change snapshot for a single Symbol."""

    symbol: Symbol
    last: Decimal
    observed_at: Instant
    quality: DataQuality
    bid: Decimal | None = None
    ask: Decimal | None = None
    volume_24h: Decimal | None = None
    change_24h_pct: Percentage | None = None
    high_24h: Decimal | None = None
    low_24h: Decimal | None = None
