"""Market data entities: Ticker, OHLCV, OrderBook, Trades, MarketSnapshot."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from cryptozavr.domain.quality import DataQuality
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import (
    Instant,
    Percentage,
    PriceSize,
    Timeframe,
    TimeRange,
)


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


@dataclass(frozen=True, slots=True)
class OHLCVCandle:
    """Single OHLCV bar. closed=True if the bar is settled (not an in-progress bar)."""

    opened_at: Instant
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    closed: bool = True


@dataclass(frozen=True, slots=True)
class OHLCVSeries:
    """Immutable sequence of candles for one (symbol, timeframe)."""

    symbol: Symbol
    timeframe: Timeframe
    candles: tuple[OHLCVCandle, ...]
    range: TimeRange
    quality: DataQuality

    def last(self) -> OHLCVCandle:
        """Return the most recent candle. Raises IndexError if series is empty."""
        return self.candles[-1]

    def window(self, n: int) -> OHLCVSeries:
        """Return a new OHLCVSeries with the last N candles."""
        n = max(0, n)
        new_candles = self.candles[-n:] if n > 0 else ()
        if not new_candles:
            new_range = self.range
        else:
            new_range = TimeRange(
                start=new_candles[0].opened_at,
                end=self.range.end,
            )
        return OHLCVSeries(
            symbol=self.symbol,
            timeframe=self.timeframe,
            candles=new_candles,
            range=new_range,
            quality=self.quality,
        )

    def slice(self, tr: TimeRange) -> OHLCVSeries:
        """Return candles whose opened_at is within [tr.start, tr.end)."""
        new_candles = tuple(c for c in self.candles if tr.contains(c.opened_at))
        return OHLCVSeries(
            symbol=self.symbol,
            timeframe=self.timeframe,
            candles=new_candles,
            range=tr,
            quality=self.quality,
        )


@dataclass(frozen=True, slots=True)
class OrderBookSnapshot:
    """Single-moment order book: bids desc by price, asks asc by price."""

    symbol: Symbol
    bids: tuple[PriceSize, ...]
    asks: tuple[PriceSize, ...]
    observed_at: Instant
    quality: DataQuality

    def best_bid(self) -> PriceSize | None:
        return self.bids[0] if self.bids else None

    def best_ask(self) -> PriceSize | None:
        return self.asks[0] if self.asks else None

    def spread(self) -> Decimal | None:
        bid = self.best_bid()
        ask = self.best_ask()
        if bid is None or ask is None:
            return None
        return ask.price - bid.price

    def spread_bps(self) -> Decimal | None:
        bid = self.best_bid()
        ask = self.best_ask()
        if bid is None or ask is None:
            return None
        mid = (ask.price + bid.price) / Decimal(2)
        if mid == 0:
            return None
        return (ask.price - bid.price) / mid * Decimal(10_000)
