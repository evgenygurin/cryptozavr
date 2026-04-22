"""Strategy-layer enums: string values are stable across releases (wire
contract for future 2D MCP tools and 2E Supabase persistence)."""

from __future__ import annotations

from cryptozavr.application.strategy.enums import (
    ComparatorOp,
    IndicatorKind,
    PriceSource,
    StrategySide,
)


def test_strategy_side_values() -> None:
    assert StrategySide.LONG.value == "long"
    assert StrategySide.SHORT.value == "short"


def test_indicator_kind_mvp_members() -> None:
    names = {k.name for k in IndicatorKind}
    assert names == {"SMA", "EMA", "RSI", "MACD", "ATR", "VOLUME"}


def test_indicator_kind_values_are_lowercase() -> None:
    for k in IndicatorKind:
        assert k.value == k.name.lower()


def test_comparator_op_includes_crossings() -> None:
    names = {op.name for op in ComparatorOp}
    assert {"GT", "GTE", "LT", "LTE", "CROSSES_ABOVE", "CROSSES_BELOW"} <= names


def test_price_source_defaults_to_close() -> None:
    assert PriceSource.CLOSE.value == "close"
    assert {s.name for s in PriceSource} >= {"OPEN", "HIGH", "LOW", "CLOSE", "HLC3"}
