"""MCP-facing DTOs. Pydantic models for tool return types."""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

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
from cryptozavr.domain.paper import (
    PaperSide,
    PaperStats,
    PaperStatus,
    PaperTrade,
)
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import PriceSize
from cryptozavr.domain.watch import (
    EventType,
    WatchEvent,
    WatchSide,
    WatchState,
    WatchStatus,
)

# 4-decimal precision (0.0001 bps) is far tighter than any venue tick size and
# avoids leaking 28-digit Decimal remainders from the domain computation.
_SPREAD_BPS_QUANTUM = Decimal("0.0001")


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
        raw_bps = snapshot.spread_bps()
        return cls(
            venue=snapshot.symbol.venue.value,
            symbol=snapshot.symbol.native_symbol,
            observed_at_ms=snapshot.observed_at.to_ms(),
            bids=[PriceSizeDTO.from_domain(b) for b in snapshot.bids],
            asks=[PriceSizeDTO.from_domain(a) for a in snapshot.asks],
            spread=snapshot.spread(),
            spread_bps=(
                raw_bps.quantize(_SPREAD_BPS_QUANTUM, rounding=ROUND_HALF_EVEN)
                if raw_bps is not None
                else None
            ),
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
    """Wire-format trending crypto asset (from CoinGecko).

    Note: `categories` is always an empty list in the current implementation.
    CoinGecko's /search/trending endpoint does not include categories, and
    the per-coin enrichment pass (/coins/{id}) is deliberately deferred to
    avoid 15x fan-out on every trending call. Clients should treat this
    field as reserved for a future release.
    """

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
        raw_id = raw.get("category_id") or raw.get("id") or ""
        raw_name = raw.get("name") or raw_id or "unknown"
        return cls(
            id=str(raw_id),
            name=str(raw_name),
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

    @model_validator(mode="after")
    def _no_partial_success(self) -> SymbolsListDTO:
        if self.error is not None and self.symbols:
            raise ValueError(
                "SymbolsListDTO: error is set but symbols is not empty — nonsense state"
            )
        return self


class TrendingListDTO(BaseModel):
    """Wire-format trending assets list (CoinGecko)."""

    model_config = ConfigDict(frozen=True)

    assets: list[TrendingAssetDTO]
    error: str | None = None

    @model_validator(mode="after")
    def _no_partial_success(self) -> TrendingListDTO:
        if self.error is not None and self.assets:
            raise ValueError(
                "TrendingListDTO: error is set but assets is not empty — nonsense state"
            )
        return self


class CategoriesListDTO(BaseModel):
    """Wire-format CoinGecko market categories list."""

    model_config = ConfigDict(frozen=True)

    categories: list[CategoryDTO]
    error: str | None = None

    @model_validator(mode="after")
    def _no_partial_success(self) -> CategoriesListDTO:
        if self.error is not None and self.categories:
            raise ValueError(
                "CategoriesListDTO: error is set but categories is not empty — nonsense state"
            )
        return self


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

    @model_validator(mode="after")
    def _venues_unique(self) -> VenueHealthDTO:
        seen: set[str] = set()
        for entry in self.venues:
            if entry.venue in seen:
                raise ValueError(f"VenueHealthDTO.venues must be unique, duplicate {entry.venue!r}")
            seen.add(entry.venue)
        return self


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


class WatchIdDTO(BaseModel):
    """Wire-format watch identifier + initial metadata."""

    model_config = ConfigDict(frozen=True)

    watch_id: str
    status: WatchStatus
    started_at_ms: int
    expected_end_at_ms: int

    @classmethod
    def from_domain(cls, state: WatchState) -> WatchIdDTO:
        return cls(
            watch_id=state.watch_id,
            status=state.status,
            started_at_ms=state.started_at_ms,
            expected_end_at_ms=(state.started_at_ms + state.max_duration_sec * 1000),
        )


class WatchEventDTO(BaseModel):
    """Wire-format single watch event."""

    model_config = ConfigDict(frozen=True)

    type: EventType
    ts_ms: int
    price: Decimal
    details: dict[str, str]

    @classmethod
    def from_domain(cls, event: WatchEvent) -> WatchEventDTO:
        return cls(
            type=event.type,
            ts_ms=event.ts_ms,
            price=event.price,
            details=dict(event.details),
        )


class WatchStateDTO(BaseModel):
    """Wire-format watch state snapshot (with event slice)."""

    model_config = ConfigDict(frozen=True)

    watch_id: str
    symbol: str
    side: WatchSide
    entry: Decimal
    stop: Decimal
    take: Decimal
    size_quote: Decimal | None
    status: WatchStatus
    current_price: Decimal | None
    last_tick_at_ms: int | None
    pnl_quote: Decimal | None
    pnl_pct: Decimal | None
    elapsed_sec: int
    events: list[WatchEventDTO]
    next_event_index: int

    @classmethod
    def from_domain(cls, state: WatchState, *, since_event_index: int = 0) -> WatchStateDTO:
        events_slice = state.events[since_event_index:]
        elapsed_ms = (state.last_tick_at_ms or state.started_at_ms) - state.started_at_ms
        return cls(
            watch_id=state.watch_id,
            symbol=state.symbol.native_symbol,
            side=state.side,
            entry=state.entry,
            stop=state.stop,
            take=state.take,
            size_quote=state.size_quote,
            status=state.status,
            current_price=state.current_price,
            last_tick_at_ms=state.last_tick_at_ms,
            pnl_quote=state.pnl_quote,
            pnl_pct=state.pnl_pct,
            elapsed_sec=max(0, elapsed_ms // 1000),
            events=[WatchEventDTO.from_domain(e) for e in events_slice],
            next_event_index=len(state.events),
        )


class PaperTradeDTO(BaseModel):
    """Wire-format paper trade record."""

    model_config = ConfigDict(frozen=True)

    id: str
    side: PaperSide
    venue: str
    symbol: str
    entry: Decimal
    stop: Decimal
    take: Decimal
    size_quote: Decimal
    opened_at_ms: int
    max_duration_sec: int
    status: PaperStatus
    exit_price: Decimal | None = None
    closed_at_ms: int | None = None
    pnl_quote: Decimal | None = None
    reason: str | None = None
    watch_id: str | None = None
    note: str | None = None

    @classmethod
    def from_domain(cls, trade: PaperTrade) -> PaperTradeDTO:
        return cls(
            id=str(trade.id),
            side=trade.side,
            venue=trade.venue,
            symbol=trade.symbol_native,
            entry=trade.entry,
            stop=trade.stop,
            take=trade.take,
            size_quote=trade.size_quote,
            opened_at_ms=trade.opened_at_ms,
            max_duration_sec=trade.max_duration_sec,
            status=trade.status,
            exit_price=trade.exit_price,
            closed_at_ms=trade.closed_at_ms,
            pnl_quote=trade.pnl_quote,
            reason=trade.reason,
            watch_id=trade.watch_id,
            note=trade.note,
        )


class PaperStatsDTO(BaseModel):
    """Wire-format paper trading statistics with live bankroll."""

    model_config = ConfigDict(frozen=True)

    trades_count: int
    wins: int
    losses: int
    open_count: int
    win_rate: Decimal
    net_pnl_quote: Decimal
    avg_win_quote: Decimal
    avg_loss_quote: Decimal
    bankroll_initial: Decimal
    bankroll_live: Decimal

    @classmethod
    def from_stats(
        cls,
        stats: PaperStats,
        *,
        bankroll_initial: Decimal,
    ) -> PaperStatsDTO:
        return cls(
            trades_count=stats.trades_count,
            wins=stats.wins,
            losses=stats.losses,
            open_count=stats.open_count,
            win_rate=stats.win_rate,
            net_pnl_quote=stats.net_pnl_quote,
            avg_win_quote=stats.avg_win_quote,
            avg_loss_quote=stats.avg_loss_quote,
            bankroll_initial=bankroll_initial,
            bankroll_live=(bankroll_initial + stats.net_pnl_quote).quantize(Decimal("0.01")),
        )
