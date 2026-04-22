"""Slippage model: price adjustment when entering/exiting a position.

LONG pays more to enter (fill >= reference), receives less to exit.
SHORT mirrors. Deterministic — same reference price always yields the
same fill.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from cryptozavr.application.strategy.enums import StrategySide

_BPS_PER_UNIT = Decimal("10000")


class SlippageModel(Protocol):
    def adjust(
        self,
        *,
        reference: Decimal,
        side: StrategySide,
        is_entry: bool,
    ) -> Decimal: ...


class PctSlippageModel:
    def __init__(self, *, bps: int = 10) -> None:
        """bps default 10 = 0.1% each side; conservative for crypto spot
        taker fills. Raises ValueError for negative bps."""
        if bps < 0:
            raise ValueError(f"bps must be >= 0 (got {bps!r})")
        self._rate = Decimal(bps) / _BPS_PER_UNIT

    def adjust(
        self,
        *,
        reference: Decimal,
        side: StrategySide,
        is_entry: bool,
    ) -> Decimal:
        # LONG entry: buy HIGHER; LONG exit: sell LOWER.
        # SHORT entry: sell LOWER; SHORT exit: buy HIGHER.
        is_buy = (side is StrategySide.LONG) == is_entry
        delta = reference * self._rate
        return reference + delta if is_buy else reference - delta
