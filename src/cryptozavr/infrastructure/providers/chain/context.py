"""Data carriers for Chain of Responsibility."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Instant, Timeframe


class FetchOperation(StrEnum):
    """Kind of fetch operation requested."""

    TICKER = "ticker"
    OHLCV = "ohlcv"
    ORDER_BOOK = "order_book"
    TRADES = "trades"


@dataclass(frozen=True, slots=True)
class FetchRequest:
    """Immutable request passed through Chain of Responsibility."""

    operation: FetchOperation
    symbol: Symbol
    timeframe: Timeframe | None = None
    since: Instant | None = None
    limit: int = 500
    depth: int = 50
    force_refresh: bool = False


@dataclass(slots=True)
class FetchContext:
    """Mutable context: accumulates reason_codes + metadata across handlers."""

    request: FetchRequest
    reason_codes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_reason(self, code: str) -> None:
        self.reason_codes.append(code)

    def has_result(self) -> bool:
        return "result" in self.metadata
