"""IndicatorRef: kind + period + price source, structurally validated."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cryptozavr.application.strategy.enums import IndicatorKind, PriceSource
from cryptozavr.application.strategy.strategy_spec import IndicatorRef


def test_minimal_indicator_ref_defaults_to_close_source() -> None:
    ref = IndicatorRef(kind=IndicatorKind.SMA, period=20)
    assert ref.source is PriceSource.CLOSE


def test_explicit_source_overrides_default() -> None:
    ref = IndicatorRef(kind=IndicatorKind.EMA, period=12, source=PriceSource.HLC3)
    assert ref.source is PriceSource.HLC3


@pytest.mark.parametrize("period", [0, -1])
def test_period_must_be_positive(period: int) -> None:
    """Only `period > 0` is enforced — no upper bound because long-lookback
    indicators (200-day SMA, 365-day MA) are legitimate."""
    with pytest.raises(ValidationError):
        IndicatorRef(kind=IndicatorKind.RSI, period=period)


def test_large_period_accepted() -> None:
    """Confirms there's no arbitrary upper bound on period (regression test
    for an earlier `le=500` cap that blocked macro-scale indicators)."""
    ref = IndicatorRef(kind=IndicatorKind.SMA, period=1000)
    assert ref.period == 1000


def test_frozen_cannot_mutate() -> None:
    ref = IndicatorRef(kind=IndicatorKind.SMA, period=20)
    with pytest.raises(ValidationError):
        ref.period = 50  # type: ignore[misc]
