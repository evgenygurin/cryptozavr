"""Wire-format DTOs for the risk MCP tools.

Mirrors domain types (TradeIntent / Violation / RiskDecision) + the
RiskPolicy DSL with primitive-typed Pydantic models so MCP clients can
build requests and consume responses as plain JSON.

Each response envelope carries a `model_validator(mode="after")` coherence
check so the server cannot emit nonsensical pairs like (error, decision)
or (success, no payload).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cryptozavr.application.risk.risk_policy import (
    LimitDecimal,
    LimitInt,
    RiskPolicy,
)
from cryptozavr.application.strategy.enums import StrategySide
from cryptozavr.domain.risk import (
    RiskDecision,
    RiskStatus,
    Severity,
    TradeIntent,
    Violation,
)
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.venues import MarketType, VenueId

# --------------------------- Input payloads ----------------------------------


class SymbolPayload(BaseModel):
    """Wire-format Symbol: primitive fields, not the domain dataclass."""

    model_config = ConfigDict(frozen=True)

    venue: VenueId
    base: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    market_type: MarketType = MarketType.SPOT
    native_symbol: str = Field(min_length=1)

    def to_domain(self) -> Symbol:
        return Symbol(
            venue=self.venue,
            base=self.base,
            quote=self.quote,
            market_type=self.market_type,
            native_symbol=self.native_symbol,
        )


class TradeIntentPayload(BaseModel):
    """Wire-format TradeIntent.

    The `symbol` field accepts EITHER:
    - a plain native-symbol string like ``"BTC-USDT"`` (recommended — a
      before-validator fills in ``venue/base/quote`` from the top-level
      ``venue`` and the "-" split); or
    - a full nested ``SymbolPayload`` object (legacy).
    """

    model_config = ConfigDict(frozen=True)

    venue: VenueId
    symbol: SymbolPayload
    side: StrategySide
    size: Decimal = Field(gt=0)
    leverage: Decimal = Field(default=Decimal(1), ge=1)
    reason: str = ""
    recent_losses: int = Field(default=0, ge=0)
    current_balance: Decimal | None = None
    current_exposure_pct: Decimal | None = None
    today_pnl_pct: Decimal | None = Field(default=None, ge=-1, le=1)

    @model_validator(mode="before")
    @classmethod
    def _coerce_flat_symbol(cls, data: Any) -> Any:
        """Allow `symbol` as a flat string like 'BTC-USDT' — expand it."""
        if not isinstance(data, dict):
            return data
        sym = data.get("symbol")
        if isinstance(sym, str):
            native = sym.strip()
            if "-" not in native:
                raise ValueError("symbol string must be in BASE-QUOTE form, e.g. 'BTC-USDT'")
            base, _, quote = native.partition("-")
            if not base or not quote:
                raise ValueError("symbol string must be non-empty BASE and QUOTE")
            venue_val = data.get("venue", "kucoin")
            data = dict(data)
            data["symbol"] = {
                "venue": venue_val,
                "base": base.upper(),
                "quote": quote.upper(),
                "market_type": "spot",
                "native_symbol": native.upper(),
            }
        return data

    @model_validator(mode="after")
    def _venue_matches(self) -> TradeIntentPayload:
        if self.venue != self.symbol.venue:
            raise ValueError(
                f"TradeIntentPayload.venue ({self.venue.value}) must match "
                f"symbol.venue ({self.symbol.venue.value})",
            )
        return self

    def to_domain(self) -> TradeIntent:
        return TradeIntent(
            venue=self.venue,
            symbol=self.symbol.to_domain(),
            side=self.side,
            size=self.size,
            leverage=self.leverage,
            reason=self.reason,
            recent_losses=self.recent_losses,
            current_balance=self.current_balance,
            current_exposure_pct=self.current_exposure_pct,
            today_pnl_pct=self.today_pnl_pct,
        )


class LimitDecimalPayload(BaseModel):
    """Wire-format LimitDecimal."""

    model_config = ConfigDict(frozen=True)

    value: Decimal = Field(gt=0)
    severity: Severity = Severity.DENY

    def to_domain(self) -> LimitDecimal:
        return LimitDecimal(value=self.value, severity=self.severity)


class LimitIntPayload(BaseModel):
    """Wire-format LimitInt."""

    model_config = ConfigDict(frozen=True)

    value: int = Field(gt=0)
    severity: Severity = Severity.DENY

    def to_domain(self) -> LimitInt:
        return LimitInt(value=self.value, severity=self.severity)


class RiskPolicyPayload(BaseModel):
    """Wire-format RiskPolicy: the five limits with per-limit severity."""

    model_config = ConfigDict(frozen=True)

    max_leverage: LimitDecimalPayload
    max_position_pct: LimitDecimalPayload
    max_daily_loss_pct: LimitDecimalPayload
    cooldown_after_n_losses: LimitIntPayload
    min_balance_buffer: LimitDecimalPayload

    def to_domain(self) -> RiskPolicy:
        return RiskPolicy(
            max_leverage=self.max_leverage.to_domain(),
            max_position_pct=self.max_position_pct.to_domain(),
            max_daily_loss_pct=self.max_daily_loss_pct.to_domain(),
            cooldown_after_n_losses=self.cooldown_after_n_losses.to_domain(),
            min_balance_buffer=self.min_balance_buffer.to_domain(),
        )


# --------------------------- Output DTOs -------------------------------------


class ViolationDTO(BaseModel):
    """Wire-format Violation."""

    model_config = ConfigDict(frozen=True)

    handler_name: str
    policy_field: str
    severity: Severity
    message: str
    observed: Decimal | int
    limit: Decimal | int

    @classmethod
    def from_domain(cls, v: Violation) -> ViolationDTO:
        return cls(
            handler_name=v.handler_name,
            policy_field=v.policy_field,
            severity=v.severity,
            message=v.message,
            observed=v.observed,
            limit=v.limit,
        )


class RiskDecisionDTO(BaseModel):
    """Wire-format RiskDecision."""

    model_config = ConfigDict(frozen=True)

    status: RiskStatus
    violations: list[ViolationDTO] = Field(default_factory=list)
    evaluated_at_ms: int

    @classmethod
    def from_domain(cls, d: RiskDecision) -> RiskDecisionDTO:
        return cls(
            status=d.status,
            violations=[ViolationDTO.from_domain(v) for v in d.violations],
            evaluated_at_ms=d.evaluated_at_ms,
        )


# --------------------------- Response envelopes ------------------------------


class SetRiskPolicyResponse(BaseModel):
    """Response for set_risk_policy.

    Coherence: either `id` is set (success) or `error` is set (failure);
    never both, never neither.
    """

    model_config = ConfigDict(frozen=True)

    id: str | None = None
    note: str = ""
    error: str | None = None

    @model_validator(mode="after")
    def _coherence(self) -> SetRiskPolicyResponse:
        if self.error is not None and self.id is not None:
            raise ValueError("SetRiskPolicyResponse: error set but id also set")
        if self.error is None and self.id is None:
            raise ValueError("SetRiskPolicyResponse: success requires id")
        return self


class GetRiskPolicyResponse(BaseModel):
    """Response for get_risk_policy.

    Coherence: error and policy are mutually exclusive. No active policy is
    a legitimate no-error state — `note` carries the explanation in that case.
    """

    model_config = ConfigDict(frozen=True)

    id: str | None = None
    policy: RiskPolicyPayload | None = None
    activated_at_ms: int | None = None
    note: str = ""
    error: str | None = None

    @model_validator(mode="after")
    def _coherence(self) -> GetRiskPolicyResponse:
        if self.error is not None and self.policy is not None:
            raise ValueError("GetRiskPolicyResponse: error set but policy present")
        return self


class EvaluateTradeIntentResponse(BaseModel):
    """Response for evaluate_trade_intent.

    Coherence: success path requires a decision; failure path emits error only.
    """

    model_config = ConfigDict(frozen=True)

    decision: RiskDecisionDTO | None = None
    error: str | None = None

    @model_validator(mode="after")
    def _coherence(self) -> EvaluateTradeIntentResponse:
        if self.error is not None and self.decision is not None:
            raise ValueError(
                "EvaluateTradeIntentResponse: error set but decision present",
            )
        if self.error is None and self.decision is None:
            raise ValueError(
                "EvaluateTradeIntentResponse: success requires decision",
            )
        return self


class SimulateRiskCheckResponse(BaseModel):
    """Response for simulate_risk_check.

    Same coherence as EvaluateTradeIntentResponse plus `policy_source` tag
    distinguishing "override" from "active".
    """

    model_config = ConfigDict(frozen=True)

    decision: RiskDecisionDTO | None = None
    policy_source: str = ""  # "active" | "override" | "" on error
    error: str | None = None

    @model_validator(mode="after")
    def _coherence(self) -> SimulateRiskCheckResponse:
        if self.error is not None and self.decision is not None:
            raise ValueError(
                "SimulateRiskCheckResponse: error set but decision present",
            )
        if self.error is None and self.decision is None:
            raise ValueError(
                "SimulateRiskCheckResponse: success requires decision",
            )
        return self


class KillSwitchStatusResponse(BaseModel):
    """Response for engage_kill_switch / disengage_kill_switch."""

    model_config = ConfigDict(frozen=True)

    engaged: bool
    engaged_at_ms: int | None = None
    reason: str | None = None
