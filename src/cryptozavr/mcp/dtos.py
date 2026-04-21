"""MCP-facing DTOs. Pydantic models for tool return types."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from cryptozavr.domain.market_data import (
    OHLCVCandle,
    OHLCVSeries,
    OrderBookSnapshot,
    Ticker,
    TradeTick,
)
from cryptozavr.domain.value_objects import PriceSize


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


class OHLCVCandleDTO(BaseModel):
    """Wire-format single OHLCV bar."""

    model_config = ConfigDict(frozen=True)

    opened_at_ms: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    closed: bool

    @classmethod
    def from_domain(cls, candle: OHLCVCandle) -> OHLCVCandleDTO:
        return cls(
            opened_at_ms=candle.opened_at.to_ms(),
            open=candle.open,
            high=candle.high,
            low=candle.low,
            close=candle.close,
            volume=candle.volume,
            closed=candle.closed,
        )


class OHLCVSeriesDTO(BaseModel):
    """Wire-format OHLCV series for the get_ohlcv MCP tool."""

    model_config = ConfigDict(frozen=True)

    venue: str
    symbol: str
    timeframe: str
    range_start_ms: int
    range_end_ms: int
    candles: list[OHLCVCandleDTO]
    staleness: str
    confidence: str
    cache_hit: bool
    reason_codes: list[str]

    @classmethod
    def from_domain(
        cls,
        series: OHLCVSeries,
        reason_codes: list[str],
    ) -> OHLCVSeriesDTO:
        return cls(
            venue=series.symbol.venue.value,
            symbol=series.symbol.native_symbol,
            timeframe=series.timeframe.value,
            range_start_ms=series.range.start.to_ms(),
            range_end_ms=series.range.end.to_ms(),
            candles=[OHLCVCandleDTO.from_domain(c) for c in series.candles],
            staleness=series.quality.staleness.name.lower(),
            confidence=series.quality.confidence.name.lower(),
            cache_hit=series.quality.cache_hit,
            reason_codes=list(reason_codes),
        )


class PriceSizeDTO(BaseModel):
    """Wire-format order-book level (price + size)."""

    model_config = ConfigDict(frozen=True)

    price: Decimal
    size: Decimal

    @classmethod
    def from_domain(cls, ps: PriceSize) -> PriceSizeDTO:
        return cls(price=ps.price, size=ps.size)


class OrderBookDTO(BaseModel):
    """Wire-format order-book snapshot for the get_order_book MCP tool."""

    model_config = ConfigDict(frozen=True)

    venue: str
    symbol: str
    observed_at_ms: int
    bids: list[PriceSizeDTO]
    asks: list[PriceSizeDTO]
    spread: Decimal | None
    spread_bps: Decimal | None
    staleness: str
    confidence: str
    cache_hit: bool
    reason_codes: list[str]

    @classmethod
    def from_domain(
        cls,
        snapshot: OrderBookSnapshot,
        reason_codes: list[str],
    ) -> OrderBookDTO:
        return cls(
            venue=snapshot.symbol.venue.value,
            symbol=snapshot.symbol.native_symbol,
            observed_at_ms=snapshot.observed_at.to_ms(),
            bids=[PriceSizeDTO.from_domain(b) for b in snapshot.bids],
            asks=[PriceSizeDTO.from_domain(a) for a in snapshot.asks],
            spread=snapshot.spread(),
            spread_bps=snapshot.spread_bps(),
            staleness=snapshot.quality.staleness.name.lower(),
            confidence=snapshot.quality.confidence.name.lower(),
            cache_hit=snapshot.quality.cache_hit,
            reason_codes=list(reason_codes),
        )


class TradeTickDTO(BaseModel):
    """Wire-format single trade tick."""

    model_config = ConfigDict(frozen=True)

    price: Decimal
    size: Decimal
    side: str
    executed_at_ms: int
    trade_id: str | None = None

    @classmethod
    def from_domain(cls, tick: TradeTick) -> TradeTickDTO:
        return cls(
            price=tick.price,
            size=tick.size,
            side=tick.side.value,
            executed_at_ms=tick.executed_at.to_ms(),
            trade_id=tick.trade_id,
        )


class TradesDTO(BaseModel):
    """Wire-format recent trades for the get_trades MCP tool."""

    model_config = ConfigDict(frozen=True)

    venue: str
    symbol: str
    trades: list[TradeTickDTO]
    reason_codes: list[str]

    @classmethod
    def from_domain(
        cls,
        *,
        venue: str,
        symbol: str,
        trades: tuple[TradeTick, ...],
        reason_codes: list[str],
    ) -> TradesDTO:
        return cls(
            venue=venue,
            symbol=symbol,
            trades=[TradeTickDTO.from_domain(t) for t in trades],
            reason_codes=list(reason_codes),
        )
