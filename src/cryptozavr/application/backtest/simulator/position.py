"""OpenPosition: immutable snapshot of an open trade."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from cryptozavr.application.strategy.enums import StrategySide


@dataclass(frozen=True, slots=True)
class OpenPosition:
    side: StrategySide
    entry_price: Decimal
    size: Decimal
    entry_bar_index: int
    take_profit_level: Decimal | None
    stop_loss_level: Decimal | None
