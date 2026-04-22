"""Indicator protocol shared by every streaming indicator.

Design notes:
- `update()` is stateful; each call advances the rolling window by one
  bar. The caller MUST feed each candle exactly once.
- Return `None` until the indicator is warm; once warm, emit `Decimal`.
  Mirrors 2C's `None`-vs-`Decimal("0")` pattern.
- No rewind / reset. Callers re-running from scratch build a fresh
  indicator instance.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from cryptozavr.domain.market_data import OHLCVCandle


class Indicator(Protocol):
    @property
    def period(self) -> int: ...

    @property
    def is_warm(self) -> bool:
        """True once the indicator has consumed enough bars to emit."""
        ...

    def update(self, candle: OHLCVCandle) -> Decimal | None:
        """Feed a new candle; return the latest value or None while warming up."""
        ...
