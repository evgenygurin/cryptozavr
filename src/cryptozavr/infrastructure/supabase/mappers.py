"""Pure functions converting Supabase rows (dict-like) to Domain entities.

No I/O. These are called by SupabaseGateway after fetching rows via asyncpg.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from cryptozavr.domain.market_data import (
    OHLCVCandle,
    OHLCVSeries,
    Ticker,
)
from cryptozavr.domain.quality import DataQuality
from cryptozavr.domain.symbols import Symbol, SymbolRegistry
from cryptozavr.domain.value_objects import (
    Instant,
    Percentage,
    Timeframe,
    TimeRange,
)
from cryptozavr.domain.venues import MarketType, VenueId


def row_to_symbol(row: Mapping[str, Any], registry: SymbolRegistry) -> Symbol:
    """Resolve a symbols row through the Flyweight registry.

    Identity is (venue, base, quote, market_type); metadata (id, active) ignored.
    """
    return registry.get(
        VenueId(row["venue_id"]),
        row["base"],
        row["quote"],
        market_type=MarketType(row["market_type"]),
        native_symbol=row["native_symbol"],
    )


def row_to_ticker(
    row: Mapping[str, Any],
    *,
    symbol: Symbol,
    quality: DataQuality,
) -> Ticker:
    """Map tickers_live row + resolved Symbol + externally-computed DataQuality."""
    change_pct_raw = row.get("change_24h_pct")
    change_pct = (
        Percentage(value=Decimal(str(change_pct_raw))) if change_pct_raw is not None else None
    )
    return Ticker(
        symbol=symbol,
        last=Decimal(str(row["last"])),
        observed_at=Instant(row["observed_at"]),
        quality=quality,
        bid=_optional_decimal(row.get("bid")),
        ask=_optional_decimal(row.get("ask")),
        volume_24h=_optional_decimal(row.get("volume_24h")),
        change_24h_pct=change_pct,
        high_24h=_optional_decimal(row.get("high_24h")),
        low_24h=_optional_decimal(row.get("low_24h")),
    )


def row_to_ohlcv_candle(row: Mapping[str, Any]) -> OHLCVCandle:
    """Map a single ohlcv_candles row."""
    return OHLCVCandle(
        opened_at=Instant(row["opened_at"]),
        open=Decimal(str(row["open"])),
        high=Decimal(str(row["high"])),
        low=Decimal(str(row["low"])),
        close=Decimal(str(row["close"])),
        volume=Decimal(str(row["volume"])),
        closed=bool(row["closed"]),
    )


def row_to_ohlcv_series(
    rows: Sequence[Mapping[str, Any]],
    *,
    symbol: Symbol,
    timeframe: Timeframe,
    quality: DataQuality,
) -> OHLCVSeries:
    """Map a list of ohlcv_candles rows into an OHLCVSeries.

    Rows must be non-empty (series range is derived from first/last opened_at).
    """
    if not rows:
        raise ValueError("row_to_ohlcv_series requires at least one row")
    candles = tuple(row_to_ohlcv_candle(r) for r in rows)
    tf_ms = timeframe.to_milliseconds()
    last_open_ms = candles[-1].opened_at.to_ms()
    series_range = TimeRange(
        start=candles[0].opened_at,
        end=Instant.from_ms(last_open_ms + tf_ms),
    )
    return OHLCVSeries(
        symbol=symbol,
        timeframe=timeframe,
        candles=candles,
        range=series_range,
        quality=quality,
    )


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))
