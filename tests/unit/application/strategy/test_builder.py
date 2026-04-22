"""StrategySpecBuilder: fluent, immutable, build() validates."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from cryptozavr.application.strategy.builder import StrategySpecBuilder
from cryptozavr.application.strategy.enums import (
    ComparatorOp,
    IndicatorKind,
    StrategySide,
)
from cryptozavr.application.strategy.strategy_spec import (
    Condition,
    IndicatorRef,
)
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.domain.venues import VenueId
from tests.unit.application.strategy.fixtures import btc_usdt_spot, valid_spec


def _entry_cond() -> Condition:
    return Condition(
        lhs=IndicatorRef(kind=IndicatorKind.EMA, period=12),
        op=ComparatorOp.CROSSES_ABOVE,
        rhs=IndicatorRef(kind=IndicatorKind.EMA, period=26),
    )


def _exit_cond() -> Condition:
    return Condition(
        lhs=IndicatorRef(kind=IndicatorKind.EMA, period=12),
        op=ComparatorOp.CROSSES_BELOW,
        rhs=IndicatorRef(kind=IndicatorKind.EMA, period=26),
    )


def _fully_built() -> StrategySpecBuilder:
    return (
        StrategySpecBuilder()
        .with_name("crossover")
        .with_description("EMA12 crossing EMA26")
        .with_market(
            venue=VenueId.KUCOIN,
            symbol=btc_usdt_spot(),
            timeframe=Timeframe.H1,
        )
        .with_entry(side=StrategySide.LONG, conditions=(_entry_cond(),))
        .with_exit(
            conditions=(_exit_cond(),),
            take_profit_pct=Decimal("0.05"),
            stop_loss_pct=Decimal("0.02"),
        )
        .with_size_pct(Decimal("0.25"))
    )


def test_builder_builds_valid_spec() -> None:
    spec = _fully_built().build()
    assert spec.name == "crossover"
    assert spec.size_pct == Decimal("0.25")


def test_builder_missing_market_rejected_at_build() -> None:
    incomplete = (
        StrategySpecBuilder()
        .with_name("x")
        .with_description("y")
        .with_entry(side=StrategySide.LONG, conditions=(_entry_cond(),))
        .with_exit(conditions=(_exit_cond(),))
        .with_size_pct(Decimal("0.1"))
    )
    with pytest.raises(ValidationError):
        incomplete.build()


def test_builder_is_immutable_per_step() -> None:
    """Each `with_*` returns a new instance; the originator is unchanged.
    Confirms partially-built specs can be shared as templates without
    accidental aliasing."""
    b1 = StrategySpecBuilder().with_name("alpha")
    b2 = b1.with_name("beta")
    assert b2 is not b1
    # Finish b1 with a different name — b2's mutation must not have leaked.
    spec_alpha = (
        b1.with_description("d")
        .with_market(
            venue=VenueId.KUCOIN,
            symbol=btc_usdt_spot(),
            timeframe=Timeframe.H1,
        )
        .with_entry(side=StrategySide.LONG, conditions=(_entry_cond(),))
        .with_exit(conditions=(_exit_cond(),))
        .with_size_pct(Decimal("0.1"))
        .build()
    )
    assert spec_alpha.name == "alpha"


def test_builder_matches_direct_construction() -> None:
    """The builder is sugar over the Pydantic constructor; the resulting
    specs must compare equal field-for-field."""
    built = (
        StrategySpecBuilder()
        .with_name("test_strategy")
        .with_description("moving-average crossover with ATR stop")
        .with_market(
            venue=VenueId.KUCOIN,
            symbol=btc_usdt_spot(),
            timeframe=Timeframe.H1,
        )
        .with_entry(side=StrategySide.LONG, conditions=(_entry_cond(),))
        .with_exit(
            conditions=(_exit_cond(),),
            take_profit_pct=Decimal("0.05"),
            stop_loss_pct=Decimal("0.02"),
        )
        .with_size_pct(Decimal("0.25"))
        .build()
    )
    assert built == valid_spec()


def test_builder_invalid_size_pct_rejected_at_build() -> None:
    """Sizing validation is deferred to `.build()` — a partially invalid
    builder is fine until the aggregate is assembled."""
    builder = _fully_built().with_size_pct(Decimal("2"))
    with pytest.raises(ValidationError):
        builder.build()


def test_builder_version_override() -> None:
    spec = _fully_built().with_version(3).build()
    assert spec.version == 3
