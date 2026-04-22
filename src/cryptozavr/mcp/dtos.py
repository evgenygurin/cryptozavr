"""MCP-facing DTOs. Pydantic models for tool return types."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from cryptozavr.application.services.market_analyzer import AnalysisReport
from cryptozavr.application.strategies.base import AnalysisResult
from cryptozavr.domain.assets import Asset
from cryptozavr.domain.market_data import (
    OHLCVCandle,
    OHLCVSeries,
    OrderBookSnapshot,
    Ticker,
    TradeTick,
)
from cryptozavr.domain.symbols import Symbol
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


class OHLCVHistoryDTO(BaseModel):
    """Wire-format streamed history for the fetch_ohlcv_history MCP tool.

    Aggregates candles from multiple paginator chunks plus the combined
    reason_codes audit trail. `chunks_fetched` lets callers see how many
    upstream calls backed the response.
    """

    model_config = ConfigDict(frozen=True)

    venue: str
    symbol: str
    timeframe: str
    range_start_ms: int
    range_end_ms: int
    candles: list[OHLCVCandleDTO]
    chunks_fetched: int
    reason_codes: list[str]

    @classmethod
    def from_chunks(
        cls,
        *,
        venue: str,
        symbol: str,
        timeframe: str,
        range_start_ms: int,
        range_end_ms: int,
        candles: list[OHLCVCandleDTO],
        chunks_fetched: int,
        reason_codes: list[str],
    ) -> OHLCVHistoryDTO:
        return cls(
            venue=venue,
            symbol=symbol,
            timeframe=timeframe,
            range_start_ms=range_start_ms,
            range_end_ms=range_end_ms,
            candles=candles,
            chunks_fetched=chunks_fetched,
            reason_codes=reason_codes,
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


class SymbolDTO(BaseModel):
    """Wire-format market symbol."""

    model_config = ConfigDict(frozen=True)

    venue: str
    base: str
    quote: str
    native_symbol: str
    market_type: str

    @classmethod
    def from_domain(cls, symbol: Symbol) -> SymbolDTO:
        return cls(
            venue=symbol.venue.value,
            base=symbol.base,
            quote=symbol.quote,
            native_symbol=symbol.native_symbol,
            market_type=symbol.market_type.value,
        )


class TrendingAssetDTO(BaseModel):
    """Wire-format trending crypto asset (from CoinGecko)."""

    model_config = ConfigDict(frozen=True)

    code: str
    name: str | None
    coingecko_id: str | None
    market_cap_rank: int | None
    categories: list[str]
    rank: int

    @classmethod
    def from_domain(cls, asset: Asset, rank: int) -> TrendingAssetDTO:
        return cls(
            code=asset.code,
            name=asset.name,
            coingecko_id=asset.coingecko_id,
            market_cap_rank=asset.market_cap_rank,
            categories=[c for c in asset.categories],
            rank=rank,
        )


class CategoryDTO(BaseModel):
    """Wire-format CoinGecko category."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    market_cap: Decimal | None = None
    market_cap_change_24h_pct: Decimal | None = None

    @classmethod
    def from_provider(cls, raw: dict[str, Any]) -> CategoryDTO:
        mc = raw.get("market_cap")
        mc_change = raw.get("market_cap_change_24h")
        return cls(
            id=str(raw["category_id"]),
            name=str(raw["name"]),
            market_cap=Decimal(str(mc)) if mc is not None else None,
            market_cap_change_24h_pct=(Decimal(str(mc_change)) if mc_change is not None else None),
        )


class VenuesListDTO(BaseModel):
    """Wire-format catalog of supported venue ids."""

    model_config = ConfigDict(frozen=True)

    venues: list[str]


class SymbolsListDTO(BaseModel):
    """Wire-format symbols-per-venue lookup."""

    model_config = ConfigDict(frozen=True)

    venue: str
    symbols: list[SymbolDTO]
    error: str | None = None


class TrendingListDTO(BaseModel):
    """Wire-format trending assets list (CoinGecko)."""

    model_config = ConfigDict(frozen=True)

    assets: list[TrendingAssetDTO]
    error: str | None = None


class CategoriesListDTO(BaseModel):
    """Wire-format CoinGecko market categories list."""

    model_config = ConfigDict(frozen=True)

    categories: list[CategoryDTO]
    error: str | None = None


class VenueHealthEntryDTO(BaseModel):
    """Per-venue health entry for the list tool / banner."""

    model_config = ConfigDict(frozen=True)

    venue: str
    state: str
    last_checked_ms: int | None = None


class VenueHealthDTO(BaseModel):
    """Wire-format venue health snapshot."""

    model_config = ConfigDict(frozen=True)

    venues: list[VenueHealthEntryDTO]


def _json_friendly(value: Any) -> Any:
    """Recursively convert tuples → lists for model_dump(mode='json') safety."""
    if isinstance(value, tuple):
        return [_json_friendly(v) for v in value]
    if isinstance(value, list):
        return [_json_friendly(v) for v in value]
    if isinstance(value, dict):
        return {k: _json_friendly(v) for k, v in value.items()}
    return value


class AnalysisResultDTO(BaseModel):
    """Wire-format single-strategy analysis result."""

    model_config = ConfigDict(frozen=True)

    strategy: str
    confidence: str
    findings: dict[str, Any]
    reason_codes: list[str]

    @classmethod
    def from_domain(
        cls,
        result: AnalysisResult,
        reason_codes: list[str],
    ) -> AnalysisResultDTO:
        return cls(
            strategy=result.strategy,
            confidence=result.confidence.name.lower(),
            findings=_json_friendly(result.findings),
            reason_codes=list(reason_codes),
        )


class AnalysisReportDTO(BaseModel):
    """Wire-format composite multi-strategy analysis report."""

    model_config = ConfigDict(frozen=True)

    venue: str
    symbol: str
    timeframe: str
    results: list[AnalysisResultDTO]
    reason_codes: list[str]

    @classmethod
    def from_domain(
        cls,
        report: AnalysisReport,
        reason_codes: list[str],
    ) -> AnalysisReportDTO:
        return cls(
            venue=report.symbol.venue.value,
            symbol=report.symbol.native_symbol,
            timeframe=report.timeframe.value,
            results=[AnalysisResultDTO.from_domain(r, reason_codes=[]) for r in report.results],
            reason_codes=list(reason_codes),
        )
