"""Synthetic OHLCVCandle stream helpers for indicator tests."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from cryptozavr.domain.market_data import OHLCVCandle
from cryptozavr.domain.value_objects import Instant

_BAR_MS = 60_000  # 1-minute candles are fine for indicator math; cadence
# is irrelevant because indicators only see `candle` fields.


def candle(
    t_index: int,
    *,
    open_: str = "100",
    high: str = "101",
    low: str = "99",
    close: str = "100",
    volume: str = "1000",
) -> OHLCVCandle:
    return OHLCVCandle(
        opened_at=Instant.from_ms(1_700_000_000_000 + t_index * _BAR_MS),
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal(volume),
    )


def closes(values: Sequence[str]) -> tuple[OHLCVCandle, ...]:
    """Candles with only `close` varying (open/high/low follow close ±1)."""
    return tuple(
        candle(
            i,
            open_=v,
            high=str(Decimal(v) + Decimal("1")),
            low=str(Decimal(v) - Decimal("1")),
            close=v,
            volume="1000",
        )
        for i, v in enumerate(values)
    )
