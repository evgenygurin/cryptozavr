"""PriceSource -> pd.Series[float] extractor.

HLC3 is computed element-wise in float64 (tolerance-checked in tests).
Float math here is intentional — the full indicator pipeline runs on
numpy for speed, with Decimal conversion happening at the evaluator
boundary.
"""

from __future__ import annotations

import pandas as pd

from cryptozavr.application.strategy.enums import PriceSource


def extract_price_series(df: pd.DataFrame, source: PriceSource) -> pd.Series:
    if source is PriceSource.OPEN:
        return df["open"]
    if source is PriceSource.HIGH:
        return df["high"]
    if source is PriceSource.LOW:
        return df["low"]
    if source is PriceSource.CLOSE:
        return df["close"]
    if source is PriceSource.HLC3:
        return (df["high"] + df["low"] + df["close"]) / 3.0
    raise ValueError(f"unhandled PriceSource: {source!r}")
