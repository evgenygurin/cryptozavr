"""Indicator Protocol shared by every streaming indicator.

All vectorized: compute() consumes a full DataFrame and returns a
pd.Series aligned to df.index with NaN during warm-up bars.
"""

from __future__ import annotations

from typing import Protocol

import pandas as pd


class Indicator(Protocol):
    @property
    def period(self) -> int: ...

    def compute(self, df: pd.DataFrame) -> pd.Series:
        """One-pass vectorized compute. NaN entries represent warm-up.
        Series dtype is float64; evaluator converts to Decimal at read
        time when comparing against Decimal constants."""
        ...
