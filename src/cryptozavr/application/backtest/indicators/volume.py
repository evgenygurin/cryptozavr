"""VolumeIndicator: identity on df['volume']."""

from __future__ import annotations

import pandas as pd


class VolumeIndicator:
    @property
    def period(self) -> int:
        return 1

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df["volume"].astype("float64")
