"""Tests for Phase 2D payload DTOs (StrategySpecPayload + response types).

Covers:
- to_domain() round-trip for each payload type.
- field validators (min_length, gt, le, NaN Decimal on Condition.rhs).
- cross-field validator on StrategySpecPayload (venue == symbol.venue).
- ValidateStrategyResponse coherence (valid vs issues).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from cryptozavr.application.strategy.enums import (
    ComparatorOp,
    IndicatorKind,
    PriceSource,
    StrategySide,
)
from cryptozavr.application.strategy.strategy_spec import (
    Condition as DomainCondition,
)
from cryptozavr.application.strategy.strategy_spec import (
    IndicatorRef as DomainIndicatorRef,
)
from cryptozavr.application.strategy.strategy_spec import (
    StrategySpec as DomainStrategySpec,
)
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Timeframe
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.mcp.tools.strategy_dtos import (
    ConditionPayload,
    IndicatorRefPayload,
    StrategyEntryPayload,
    StrategyExitPayload,
    StrategySpecPayload,
    SymbolPayload,
    ValidateStrategyResponse,
    ValidationIssueDTO,
)


def _valid_spec_payload_dict() -> dict:
    """Minimal valid payload dict for round-trip tests."""
    return {
        "name": "sma-cross",
        "description": "fast-over-slow SMA cross",
        "venue": "kucoin",
        "symbol": {
            "venue": "kucoin",
            "base": "BTC",
            "quote": "USDT",
            "market_type": "spot",
            "native_symbol": "BTC-USDT",
        },
        "timeframe": "1h",
        "entry": {
            "side": "long",
            "conditions": [
                {
                    "lhs": {"kind": "sma", "period": 10, "source": "close"},
                    "op": "gt",
                    "rhs": {"kind": "sma", "period": 50, "source": "close"},
                },
            ],
        },
        "exit": {
            "conditions": [],
            "take_profit_pct": "0.05",
            "stop_loss_pct": "0.02",
        },
        "size_pct": "0.25",
        "version": 1,
    }


class TestSymbolPayload:
    def test_to_domain_returns_symbol_with_matching_identity(self) -> None:
        payload = SymbolPayload(
            venue=VenueId.KUCOIN,
            base="BTC",
            quote="USDT",
            market_type=MarketType.SPOT,
            native_symbol="BTC-USDT",
        )
        sym = payload.to_domain()
        assert isinstance(sym, Symbol)
        assert sym.venue is VenueId.KUCOIN
        assert sym.base == "BTC"
        assert sym.quote == "USDT"
        assert sym.market_type is MarketType.SPOT
        assert sym.native_symbol == "BTC-USDT"

    def test_to_domain_raises_on_lowercase_base(self) -> None:
        # Symbol.__post_init__ enforces uppercase base. Payload layer allows
        # any non-empty string (validation is deferred to to_domain). The
        # domain-level exception surfaces as ValidationError.
        payload = SymbolPayload(
            venue=VenueId.KUCOIN,
            base="btc",
            quote="USDT",
            market_type=MarketType.SPOT,
            native_symbol="btc-USDT",
        )
        with pytest.raises(Exception):  # noqa: B017,PT011 — domain ValidationError
            payload.to_domain()


class TestIndicatorRefPayload:
    def test_to_domain_mirrors_fields(self) -> None:
        payload = IndicatorRefPayload(kind=IndicatorKind.SMA, period=14, source=PriceSource.CLOSE)
        dom = payload.to_domain()
        assert isinstance(dom, DomainIndicatorRef)
        assert dom.kind is IndicatorKind.SMA
        assert dom.period == 14
        assert dom.source is PriceSource.CLOSE

    def test_non_positive_period_fails_validation(self) -> None:
        with pytest.raises(ValidationError):
            IndicatorRefPayload(kind=IndicatorKind.SMA, period=0)


class TestConditionPayload:
    def test_indicator_ref_rhs_roundtrips(self) -> None:
        payload = ConditionPayload(
            lhs=IndicatorRefPayload(kind=IndicatorKind.SMA, period=10),
            op=ComparatorOp.GT,
            rhs=IndicatorRefPayload(kind=IndicatorKind.SMA, period=50),
        )
        dom = payload.to_domain()
        assert isinstance(dom, DomainCondition)
        assert isinstance(dom.rhs, DomainIndicatorRef)
        assert dom.op is ComparatorOp.GT
        assert dom.rhs.period == 50

    def test_decimal_rhs_roundtrips(self) -> None:
        payload = ConditionPayload(
            lhs=IndicatorRefPayload(kind=IndicatorKind.RSI, period=14),
            op=ComparatorOp.LT,
            rhs=Decimal("30"),
        )
        dom = payload.to_domain()
        assert isinstance(dom.rhs, Decimal)
        assert dom.rhs == Decimal("30")

    def test_nan_decimal_rhs_fails_validation(self) -> None:
        with pytest.raises(ValidationError):
            ConditionPayload(
                lhs=IndicatorRefPayload(kind=IndicatorKind.RSI, period=14),
                op=ComparatorOp.LT,
                rhs=Decimal("NaN"),
            )


class TestStrategyEntryPayload:
    def test_empty_conditions_fails_validation(self) -> None:
        with pytest.raises(ValidationError):
            StrategyEntryPayload(side=StrategySide.LONG, conditions=())


class TestStrategyExitPayload:
    def test_to_domain_requires_bail_out(self) -> None:
        # Payload layer itself allows the empty shell (no conditions, no TP/SL);
        # domain StrategyExit enforces at-least-one bail-out in its model_validator.
        payload = StrategyExitPayload(conditions=())
        with pytest.raises(ValidationError):
            payload.to_domain()


class TestStrategySpecPayload:
    def test_to_domain_builds_full_domain_spec(self) -> None:
        payload = StrategySpecPayload.model_validate(_valid_spec_payload_dict())
        dom = payload.to_domain()
        assert isinstance(dom, DomainStrategySpec)
        assert dom.name == "sma-cross"
        assert dom.venue is VenueId.KUCOIN
        assert dom.symbol.native_symbol == "BTC-USDT"
        assert dom.timeframe is Timeframe.H1
        assert dom.entry.side is StrategySide.LONG
        assert dom.size_pct == Decimal("0.25")

    def test_venue_mismatch_with_symbol_venue_fails(self) -> None:
        raw = _valid_spec_payload_dict()
        raw["venue"] = "coingecko"  # symbol.venue still "kucoin"
        with pytest.raises(ValidationError) as excinfo:
            StrategySpecPayload.model_validate(raw)
        assert "venue" in str(excinfo.value).lower()

    def test_size_pct_zero_fails(self) -> None:
        raw = _valid_spec_payload_dict()
        raw["size_pct"] = "0"
        with pytest.raises(ValidationError):
            StrategySpecPayload.model_validate(raw)

    def test_size_pct_greater_than_one_fails(self) -> None:
        raw = _valid_spec_payload_dict()
        raw["size_pct"] = "1.5"
        with pytest.raises(ValidationError):
            StrategySpecPayload.model_validate(raw)


class TestValidateStrategyResponseCoherence:
    def test_valid_true_with_issues_raises(self) -> None:
        with pytest.raises(ValidationError):
            ValidateStrategyResponse(
                valid=True,
                issues=[ValidationIssueDTO(location=["x"], message="m", type="t")],
            )

    def test_valid_false_without_issues_raises(self) -> None:
        with pytest.raises(ValidationError):
            ValidateStrategyResponse(valid=False, issues=[])

    def test_valid_true_no_issues_ok(self) -> None:
        resp = ValidateStrategyResponse(valid=True, issues=[])
        assert resp.valid is True
        assert resp.issues == []
