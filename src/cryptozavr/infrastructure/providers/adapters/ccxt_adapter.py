"""CCXTAdapter: raw CCXT unified dict → Domain entities.

Pure functions. No I/O.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from cryptozavr.domain.market_data import (
    OHLCVCandle,
    OHLCVSeries,
    OrderBookSnapshot,
    Ticker,
)
from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import (
    Instant,
    Percentage,
    PriceSize,
    Timeframe,
    TimeRange,
)


class CCXTAdapter:
    """Static conversions from CCXT unified format to Domain entities."""

    @staticmethod
    def ticker_to_domain(raw: Mapping[str, Any], symbol: Symbol) -> Ticker:
        observed_ms = int(raw.get("timestamp") or 0)
        observed_at = Instant.from_ms(observed_ms) if observed_ms else Instant.now()
        quality = _fresh_quality(symbol, endpoint="fetch_ticker")
        return Ticker(
            symbol=symbol,
            last=_decimal(raw["last"]),
            observed_at=observed_at,
            quality=quality,
            bid=_optional_decimal(raw.get("bid")),
            ask=_optional_decimal(raw.get("ask")),
            volume_24h=_optional_decimal(raw.get("baseVolume")),
            change_24h_pct=(
                Percentage(value=_decimal(raw["percentage"]))
                if raw.get("percentage") is not None
                else None
            ),
            high_24h=_optional_decimal(raw.get("high")),
            low_24h=_optional_decimal(raw.get("low")),
        )

    @staticmethod
    def ohlcv_to_series(
        raw: Sequence[Sequence[Any]],
        symbol: Symbol,
        timeframe: Timeframe,
    ) -> OHLCVSeries:
        if not raw:
            raise ValueError("ohlcv_to_series received an empty list")
        candles = tuple(
            OHLCVCandle(
                opened_at=Instant.from_ms(int(row[0])),
                open=_decimal(row[1]),
                high=_decimal(row[2]),
                low=_decimal(row[3]),
                close=_decimal(row[4]),
                volume=_decimal(row[5]),
                closed=True,
            )
            for row in raw
        )
        tf_ms = timeframe.to_milliseconds()
        last_ms = candles[-1].opened_at.to_ms()
        series_range = TimeRange(
            start=candles[0].opened_at,
            end=Instant.from_ms(last_ms + tf_ms),
        )
        return OHLCVSeries(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
            range=series_range,
            quality=_fresh_quality(symbol, endpoint="fetch_ohlcv"),
        )

    @staticmethod
    def orderbook_to_domain(
        raw: Mapping[str, Any],
        symbol: Symbol,
    ) -> OrderBookSnapshot:
        observed_ms = int(raw.get("timestamp") or 0)
        observed_at = Instant.from_ms(observed_ms) if observed_ms else Instant.now()
        bids = tuple(
            PriceSize(price=_decimal(level[0]), size=_decimal(level[1]))
            for level in raw.get("bids", [])
        )
        asks = tuple(
            PriceSize(price=_decimal(level[0]), size=_decimal(level[1]))
            for level in raw.get("asks", [])
        )
        return OrderBookSnapshot(
            symbol=symbol,
            bids=bids,
            asks=asks,
            observed_at=observed_at,
            quality=_fresh_quality(symbol, endpoint="fetch_order_book"),
        )


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _fresh_quality(symbol: Symbol, *, endpoint: str) -> DataQuality:
    return DataQuality(
        source=Provenance(venue_id=symbol.venue.value, endpoint=endpoint),
        fetched_at=Instant.now(),
        staleness=Staleness.FRESH,
        confidence=Confidence.HIGH,
        cache_hit=False,
    )
