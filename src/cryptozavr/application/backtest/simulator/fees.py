"""Fee model: per-fill charge, deducted from equity."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

_BPS_PER_UNIT = Decimal("10000")


class FeeModel(Protocol):
    def compute(self, *, notional: Decimal, is_entry: bool) -> Decimal: ...


class FixedBpsFeeModel:
    def __init__(self, *, bps: int = 5) -> None:
        if bps < 0:
            raise ValueError(f"bps must be >= 0 (got {bps!r})")
        self._rate = Decimal(bps) / _BPS_PER_UNIT

    def compute(self, *, notional: Decimal, is_entry: bool) -> Decimal:
        return notional * self._rate
