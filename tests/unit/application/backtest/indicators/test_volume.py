"""VolumeIndicator: identity on df['volume']."""

from __future__ import annotations

import pandas as pd

from cryptozavr.application.backtest.indicators.volume import VolumeIndicator
from tests.unit.application.backtest.fixtures import candle_df


def test_returns_volume_series() -> None:
    v = VolumeIndicator()
    df = candle_df(["100", "105"], volume="1234.5")
    series = v.compute(df)
    assert list(series) == [1234.5, 1234.5]


def test_no_warm_up_period_one() -> None:
    assert VolumeIndicator().period == 1


def test_different_volumes_per_bar() -> None:
    """Manually build a DataFrame with varying volume."""
    df = pd.DataFrame(
        {
            "open": [1.0, 1.0],
            "high": [2.0, 2.0],
            "low": [0.5, 0.5],
            "close": [1.0, 1.0],
            "volume": [100.0, 250.0],
        }
    )
    series = VolumeIndicator().compute(df)
    assert list(series) == [100.0, 250.0]
