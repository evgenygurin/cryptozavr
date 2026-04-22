"""Shared test fixture: build a candle DataFrame from close prices."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from decimal import Decimal

import pandas as pd


def candle_df(
    closes: Sequence[str],
    *,
    high_bump: str = "1",
    low_bump: str = "1",
    volume: str = "1000",
) -> pd.DataFrame:
    """Build a DataFrame with len(closes) bars. Open == close for each bar;
    high = close + high_bump, low = close - low_bump. Timestamps are
    contiguous 1-minute UTC.

    Returned columns: open, high, low, close, volume, timestamp (dtype
    datetime64[ns, UTC] via pd.Timestamp). Numeric columns are float64.
    """
    start = dt.datetime(2026, 1, 1, 0, 0, 0, tzinfo=dt.UTC)
    rows = []
    for i, c in enumerate(closes):
        close_d = Decimal(c)
        rows.append(
            {
                "timestamp": start + dt.timedelta(minutes=i),
                "open": float(close_d),
                "high": float(close_d + Decimal(high_bump)),
                "low": float(close_d - Decimal(low_bump)),
                "close": float(close_d),
                "volume": float(Decimal(volume)),
            }
        )
    return pd.DataFrame(rows)
