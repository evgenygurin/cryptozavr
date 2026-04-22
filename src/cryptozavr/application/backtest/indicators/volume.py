"""VolumeIndicator: identity on candle.volume.

Exists so the factory can return an `Indicator` uniformly even when
strategies reference `VOLUME > threshold`. Warms up after the first bar.
"""

from __future__ import annotations

from decimal import Decimal

from cryptozavr.domain.market_data import OHLCVCandle


class VolumeIndicator:
    def __init__(self) -> None:
        self._latest: Decimal | None = None

    @property
    def period(self) -> int:
        return 1

    @property
    def is_warm(self) -> bool:
        return self._latest is not None

    def update(self, candle: OHLCVCandle) -> Decimal | None:
        self._latest = candle.volume
        return self._latest
