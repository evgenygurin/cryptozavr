"""StrategySpec: the aggregate DTO + its invariants + round-trip."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from cryptozavr.application.strategy.strategy_spec import StrategySpec
from tests.unit.application.strategy.fixtures import valid_spec


def test_happy_path_instance_is_valid() -> None:
    spec = valid_spec()
    assert spec.name == "test_strategy"
    assert spec.size_pct == Decimal("0.25")


def test_name_empty_rejected() -> None:
    with pytest.raises(ValidationError):
        valid_spec(name="")


def test_size_pct_zero_rejected() -> None:
    with pytest.raises(ValidationError):
        valid_spec(size_pct=Decimal("0"))


def test_size_pct_above_one_rejected() -> None:
    with pytest.raises(ValidationError):
        valid_spec(size_pct=Decimal("1.5"))


def test_version_defaults_to_one() -> None:
    spec = valid_spec()
    assert spec.version == 1


def test_model_copy_update_produces_new_instance() -> None:
    original = valid_spec()
    cloned = original.model_copy(update={"name": "cloned"})
    assert original.name == "test_strategy"
    assert cloned.name == "cloned"
    assert original.version == cloned.version


def test_frozen_cannot_mutate() -> None:
    spec = valid_spec()
    with pytest.raises(ValidationError):
        spec.name = "new_name"  # type: ignore[misc]


def test_round_trip_through_model_dump_model_validate() -> None:
    """Pydantic serialisation + deserialisation is lossless for StrategySpec.
    `arbitrary_types_allowed=True` plus `Symbol` being a frozen dataclass
    makes this non-trivial — verify that `Symbol` serialises and revives."""
    spec = valid_spec()
    native = spec.model_dump()
    revived = StrategySpec.model_validate(native)
    assert revived == spec


def test_description_overlong_rejected() -> None:
    with pytest.raises(ValidationError):
        valid_spec(description="x" * 1025)


def test_name_overlong_rejected() -> None:
    with pytest.raises(ValidationError):
        valid_spec(name="x" * 129)


def test_version_zero_rejected() -> None:
    with pytest.raises(ValidationError):
        valid_spec(version=0)
