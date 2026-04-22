"""Fluent, immutable builder for StrategySpec.

Each `with_*` returns a new builder so partially-built specs don't alias.
Validation is deferred to `.build()` which constructs the full StrategySpec
in one shot — Pydantic validates the aggregate atomically, so the error
surface matches direct construction and 2D MCP callers see identical
diagnostics regardless of path.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Self

from cryptozavr.application.strategy.enums import StrategySide
from cryptozavr.application.strategy.strategy_spec import (
    Condition,
    StrategyEntry,
    StrategyExit,
    StrategySpec,
)
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.domain.venues import VenueId


@dataclass(frozen=True, slots=True)
class StrategySpecBuilder:
    _name: str | None = None
    _description: str | None = None
    _venue: VenueId | None = None
    _symbol: Symbol | None = None
    _timeframe: Timeframe | None = None
    _entry: StrategyEntry | None = None
    _exit: StrategyExit | None = None
    _size_pct: Decimal | None = None
    _version: int = 1

    def with_name(self, name: str) -> Self:
        return replace(self, _name=name)

    def with_description(self, description: str) -> Self:
        return replace(self, _description=description)

    def with_market(
        self,
        *,
        venue: VenueId,
        symbol: Symbol,
        timeframe: Timeframe,
    ) -> Self:
        return replace(self, _venue=venue, _symbol=symbol, _timeframe=timeframe)

    def with_entry(
        self,
        *,
        side: StrategySide,
        conditions: Iterable[Condition],
    ) -> Self:
        return replace(
            self,
            _entry=StrategyEntry(side=side, conditions=tuple(conditions)),
        )

    def with_exit(
        self,
        *,
        conditions: Iterable[Condition] = (),
        take_profit_pct: Decimal | None = None,
        stop_loss_pct: Decimal | None = None,
    ) -> Self:
        return replace(
            self,
            _exit=StrategyExit(
                conditions=tuple(conditions),
                take_profit_pct=take_profit_pct,
                stop_loss_pct=stop_loss_pct,
            ),
        )

    def with_size_pct(self, pct: Decimal) -> Self:
        return replace(self, _size_pct=pct)

    def with_version(self, version: int) -> Self:
        return replace(self, _version=version)

    def build(self) -> StrategySpec:
        # Pydantic raises ValidationError for any None where the field is
        # required — so the error surface matches direct construction and
        # 2D MCP callers see the same diagnostics.
        return StrategySpec(
            name=self._name,  # type: ignore[arg-type]
            description=self._description,  # type: ignore[arg-type]
            venue=self._venue,  # type: ignore[arg-type]
            symbol=self._symbol,  # type: ignore[arg-type]
            timeframe=self._timeframe,  # type: ignore[arg-type]
            entry=self._entry,  # type: ignore[arg-type]
            exit=self._exit,  # type: ignore[arg-type]
            size_pct=self._size_pct,  # type: ignore[arg-type]
            version=self._version,
        )
