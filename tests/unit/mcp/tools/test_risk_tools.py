"""Unit tests for Phase 3 Unit 3-3 risk MCP tools.

Covers the six tools registered by `register_risk_tools(mcp)`:

- set_risk_policy / get_risk_policy
- evaluate_trade_intent / simulate_risk_check
- engage_kill_switch / disengage_kill_switch

We use `MagicMock(spec=...)` for the three lifespan dependencies
(RiskEngine / KillSwitch / RiskPolicyRepository) because FastMCP's
Depends resolver treats any object exposing `__aenter__` as an
``async with`` candidate — a bare MagicMock would trip that path.
The `spec=` constraint hides dunder synthesis.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from cryptozavr.application.risk.engine import RiskEngine
from cryptozavr.application.risk.kill_switch import KillSwitch, KillSwitchStatus
from cryptozavr.application.risk.risk_policy import (
    LimitDecimal,
    LimitInt,
    RiskPolicy,
)
from cryptozavr.domain.risk import (
    RiskDecision,
    RiskStatus,
    Severity,
    Violation,
)
from cryptozavr.infrastructure.persistence.risk_policy_repo import (
    RiskPolicyRepository,
    RiskPolicyRow,
)
from cryptozavr.mcp.lifespan_state import LIFESPAN_KEYS
from cryptozavr.mcp.tools.risk_dtos import (
    EvaluateTradeIntentResponse,
    GetRiskPolicyResponse,
    KillSwitchStatusResponse,
    LimitDecimalPayload,
    LimitIntPayload,
    RiskDecisionDTO,
    RiskPolicyPayload,
    SetRiskPolicyResponse,
    SimulateRiskCheckResponse,
)
from cryptozavr.mcp.tools.risk_tools import register_risk_tools

# ----------------------------- helpers ---------------------------------------


def _structured(result) -> dict:  # type: ignore[no-untyped-def]
    sc = getattr(result, "structured_content", None)
    if sc is not None:
        return sc
    return json.loads(result.content[0].text)


def _valid_policy_payload() -> dict:
    return {
        "max_leverage": {"value": "3", "severity": "deny"},
        "max_position_pct": {"value": "0.25", "severity": "deny"},
        "max_daily_loss_pct": {"value": "0.05", "severity": "warn"},
        "cooldown_after_n_losses": {"value": 3, "severity": "warn"},
        "min_balance_buffer": {"value": "100", "severity": "deny"},
    }


def _valid_intent_payload() -> dict:
    return {
        "venue": "kucoin",
        "symbol": {
            "venue": "kucoin",
            "base": "BTC",
            "quote": "USDT",
            "market_type": "spot",
            "native_symbol": "BTC-USDT",
        },
        "side": "long",
        "size": "100",
        "leverage": "2",
        "reason": "unit-test",
        "recent_losses": 0,
        "current_balance": "1000",
    }


def _make_policy_row(*, is_active: bool = True) -> RiskPolicyRow:
    policy = RiskPolicy(
        max_leverage=LimitDecimal(value=Decimal("3"), severity=Severity.DENY),
        max_position_pct=LimitDecimal(value=Decimal("0.25"), severity=Severity.DENY),
        max_daily_loss_pct=LimitDecimal(value=Decimal("0.05"), severity=Severity.WARN),
        cooldown_after_n_losses=LimitInt(value=3, severity=Severity.WARN),
        min_balance_buffer=LimitDecimal(value=Decimal("100"), severity=Severity.DENY),
    )
    return RiskPolicyRow(
        id=uuid4(),
        policy=policy,
        is_active=is_active,
        created_at_ms=1_700_000_000_000,
        activated_at_ms=1_700_000_060_000 if is_active else None,
    )


def _ok_decision() -> RiskDecision:
    return RiskDecision(status=RiskStatus.OK, violations=(), evaluated_at_ms=1_700_000_000_000)


def _deny_decision() -> RiskDecision:
    v = Violation(
        handler_name="RiskPolicy",
        policy_field="max_leverage",
        severity=Severity.DENY,
        message="leverage 5 exceeds max_leverage 3",
        observed=Decimal("5"),
        limit=Decimal("3"),
    )
    return RiskDecision(
        status=RiskStatus.DENY,
        violations=(v,),
        evaluated_at_ms=1_700_000_000_000,
    )


def _mock_engine(decision: RiskDecision | None = None) -> MagicMock:
    engine = MagicMock(spec=RiskEngine)
    engine.evaluate = MagicMock(return_value=decision or _ok_decision())
    return engine


def _mock_kill_switch() -> MagicMock:
    ks = MagicMock(spec=KillSwitch)
    ks.engage = MagicMock(
        return_value=KillSwitchStatus(
            engaged=True,
            engaged_at_ms=1_700_000_000_000,
            reason="manual",
        ),
    )
    ks.disengage = MagicMock(
        return_value=KillSwitchStatus(
            engaged=False,
            engaged_at_ms=None,
            reason=None,
        ),
    )
    ks.status = MagicMock(
        return_value=KillSwitchStatus(
            engaged=False,
            engaged_at_ms=None,
            reason=None,
        ),
    )
    ks.is_engaged = MagicMock(return_value=False)
    return ks


def _mock_repo(
    *,
    save_return: object | None = None,
    save_side_effect: BaseException | None = None,
    activate_side_effect: BaseException | None = None,
    get_active_return: RiskPolicyRow | None = None,
    get_active_side_effect: BaseException | None = None,
) -> MagicMock:
    repo = MagicMock(spec=RiskPolicyRepository)
    if save_side_effect is not None:
        repo.save = AsyncMock(side_effect=save_side_effect)
    else:
        repo.save = AsyncMock(return_value=save_return)
    if activate_side_effect is not None:
        repo.activate = AsyncMock(side_effect=activate_side_effect)
    else:
        repo.activate = AsyncMock(return_value=None)
    if get_active_side_effect is not None:
        repo.get_active = AsyncMock(side_effect=get_active_side_effect)
    else:
        repo.get_active = AsyncMock(return_value=get_active_return)
    return repo


def _build_server(
    *,
    engine: MagicMock | None = None,
    kill_switch: MagicMock | None = None,
    repo: MagicMock | None = None,
) -> FastMCP:
    effective_engine = engine if engine is not None else _mock_engine()
    effective_ks = kill_switch if kill_switch is not None else _mock_kill_switch()
    effective_repo = repo if repo is not None else _mock_repo(save_return=uuid4())

    @asynccontextmanager
    async def lifespan(_server):  # type: ignore[no-untyped-def]
        yield {
            LIFESPAN_KEYS.risk_engine: effective_engine,
            LIFESPAN_KEYS.kill_switch: effective_ks,
            LIFESPAN_KEYS.risk_policy_repo: effective_repo,
        }

    mcp = FastMCP(name="t", version="0", lifespan=lifespan)
    register_risk_tools(mcp)
    return mcp


# ============================= set_risk_policy ===============================


class TestSetRiskPolicy:
    @pytest.mark.asyncio
    async def test_valid_payload_returns_id_and_saved_note(self) -> None:
        new_id = uuid4()
        repo = _mock_repo(save_return=new_id)
        mcp = _build_server(repo=repo)
        async with Client(mcp) as client:
            result = await client.call_tool(
                "set_risk_policy",
                {"policy": _valid_policy_payload()},
            )
        payload = _structured(result)
        assert payload["id"] == str(new_id)
        assert payload["note"] == "saved and activated"
        assert payload["error"] is None
        repo.save.assert_awaited_once()
        repo.activate.assert_awaited_once_with(new_id)

    @pytest.mark.asyncio
    async def test_missing_field_returns_error_with_location(self) -> None:
        repo = _mock_repo(save_return=uuid4())
        mcp = _build_server(repo=repo)
        bad = _valid_policy_payload()
        del bad["max_leverage"]
        async with Client(mcp) as client:
            result = await client.call_tool(
                "set_risk_policy",
                {"policy": bad},
            )
        payload = _structured(result)
        assert payload["id"] is None
        assert payload["error"] is not None
        assert "max_leverage" in payload["error"]
        repo.save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_repo_failure_surfaces_in_error(self) -> None:
        repo = _mock_repo(save_side_effect=RuntimeError("pg down"))
        mcp = _build_server(repo=repo)
        async with Client(mcp) as client:
            result = await client.call_tool(
                "set_risk_policy",
                {"policy": _valid_policy_payload()},
            )
        payload = _structured(result)
        assert payload["id"] is None
        assert payload["error"] is not None
        assert "RuntimeError" in payload["error"]

    @pytest.mark.asyncio
    async def test_structured_content_populated(self) -> None:
        repo = _mock_repo(save_return=uuid4())
        mcp = _build_server(repo=repo)
        async with Client(mcp) as client:
            result = await client.call_tool(
                "set_risk_policy",
                {"policy": _valid_policy_payload()},
            )
        sc = getattr(result, "structured_content", None)
        if sc is not None:
            assert "id" in sc
            assert "note" in sc
            assert "error" in sc


# ============================= get_risk_policy ===============================


class TestGetRiskPolicy:
    @pytest.mark.asyncio
    async def test_no_active_returns_note_and_null_policy(self) -> None:
        repo = _mock_repo(get_active_return=None)
        mcp = _build_server(repo=repo)
        async with Client(mcp) as client:
            result = await client.call_tool("get_risk_policy", {})
        payload = _structured(result)
        assert payload["id"] is None
        assert payload["policy"] is None
        assert "no active risk policy" in payload["note"]
        assert payload["error"] is None

    @pytest.mark.asyncio
    async def test_active_returns_id_and_policy(self) -> None:
        row = _make_policy_row(is_active=True)
        repo = _mock_repo(get_active_return=row)
        mcp = _build_server(repo=repo)
        async with Client(mcp) as client:
            result = await client.call_tool("get_risk_policy", {})
        payload = _structured(result)
        assert payload["id"] == str(row.id)
        assert payload["policy"] is not None
        assert payload["policy"]["max_leverage"]["value"] == "3"
        assert payload["activated_at_ms"] == row.activated_at_ms
        assert payload["note"] == "active"
        assert payload["error"] is None

    @pytest.mark.asyncio
    async def test_repo_failure_surfaces_in_error(self) -> None:
        repo = _mock_repo(get_active_side_effect=RuntimeError("pg down"))
        mcp = _build_server(repo=repo)
        async with Client(mcp) as client:
            result = await client.call_tool("get_risk_policy", {})
        payload = _structured(result)
        assert payload["error"] is not None
        assert "RuntimeError" in payload["error"]


# ========================== evaluate_trade_intent ============================


class TestEvaluateTradeIntent:
    @pytest.mark.asyncio
    async def test_no_active_policy_returns_error(self) -> None:
        repo = _mock_repo(get_active_return=None)
        mcp = _build_server(repo=repo)
        async with Client(mcp) as client:
            result = await client.call_tool(
                "evaluate_trade_intent",
                {"intent": _valid_intent_payload()},
            )
        payload = _structured(result)
        assert payload["decision"] is None
        assert "no active risk policy" in payload["error"]

    @pytest.mark.asyncio
    async def test_malformed_intent_returns_error_with_location(self) -> None:
        row = _make_policy_row()
        repo = _mock_repo(get_active_return=row)
        mcp = _build_server(repo=repo)
        bad = _valid_intent_payload()
        del bad["size"]
        async with Client(mcp) as client:
            result = await client.call_tool(
                "evaluate_trade_intent",
                {"intent": bad},
            )
        payload = _structured(result)
        assert payload["decision"] is None
        assert payload["error"] is not None
        assert "size" in payload["error"]

    @pytest.mark.asyncio
    async def test_ok_intent_returns_decision(self) -> None:
        row = _make_policy_row()
        repo = _mock_repo(get_active_return=row)
        engine = _mock_engine(_ok_decision())
        mcp = _build_server(engine=engine, repo=repo)
        async with Client(mcp) as client:
            result = await client.call_tool(
                "evaluate_trade_intent",
                {"intent": _valid_intent_payload()},
            )
        payload = _structured(result)
        assert payload["error"] is None
        assert payload["decision"]["status"] == "ok"
        assert payload["decision"]["violations"] == []
        engine.evaluate.assert_called_once()

    @pytest.mark.asyncio
    async def test_deny_decision_propagates_violations(self) -> None:
        row = _make_policy_row()
        repo = _mock_repo(get_active_return=row)
        engine = _mock_engine(_deny_decision())
        mcp = _build_server(engine=engine, repo=repo)
        async with Client(mcp) as client:
            result = await client.call_tool(
                "evaluate_trade_intent",
                {"intent": _valid_intent_payload()},
            )
        payload = _structured(result)
        assert payload["decision"]["status"] == "deny"
        assert len(payload["decision"]["violations"]) == 1
        assert payload["decision"]["violations"][0]["handler_name"] == "RiskPolicy"

    @pytest.mark.asyncio
    async def test_repo_failure_surfaces_in_error(self) -> None:
        repo = _mock_repo(get_active_side_effect=RuntimeError("pg down"))
        mcp = _build_server(repo=repo)
        async with Client(mcp) as client:
            result = await client.call_tool(
                "evaluate_trade_intent",
                {"intent": _valid_intent_payload()},
            )
        payload = _structured(result)
        assert payload["error"] is not None
        assert "RuntimeError" in payload["error"]


# ========================== simulate_risk_check ==============================


class TestSimulateRiskCheck:
    @pytest.mark.asyncio
    async def test_override_used_and_flagged(self) -> None:
        # No active policy — but override is provided, so it should still run.
        repo = _mock_repo(get_active_return=None)
        engine = _mock_engine(_ok_decision())
        mcp = _build_server(engine=engine, repo=repo)
        async with Client(mcp) as client:
            result = await client.call_tool(
                "simulate_risk_check",
                {
                    "payload": {
                        "intent": _valid_intent_payload(),
                        "policy_override": _valid_policy_payload(),
                    },
                },
            )
        payload = _structured(result)
        assert payload["error"] is None
        assert payload["policy_source"] == "override"
        engine.evaluate.assert_called_once()
        # Repo get_active must NOT be called when override is set.
        repo.get_active.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_override_falls_back_to_active(self) -> None:
        row = _make_policy_row()
        repo = _mock_repo(get_active_return=row)
        engine = _mock_engine(_ok_decision())
        mcp = _build_server(engine=engine, repo=repo)
        async with Client(mcp) as client:
            result = await client.call_tool(
                "simulate_risk_check",
                {"payload": {"intent": _valid_intent_payload()}},
            )
        payload = _structured(result)
        assert payload["error"] is None
        assert payload["policy_source"] == "active"
        repo.get_active.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_override_no_active_returns_error(self) -> None:
        repo = _mock_repo(get_active_return=None)
        engine = _mock_engine(_ok_decision())
        mcp = _build_server(engine=engine, repo=repo)
        async with Client(mcp) as client:
            result = await client.call_tool(
                "simulate_risk_check",
                {"payload": {"intent": _valid_intent_payload()}},
            )
        payload = _structured(result)
        assert payload["decision"] is None
        assert "no active risk policy" in payload["error"]

    @pytest.mark.asyncio
    async def test_malformed_override_returns_error(self) -> None:
        engine = _mock_engine(_ok_decision())
        mcp = _build_server(engine=engine)
        bad_override = _valid_policy_payload()
        del bad_override["max_leverage"]
        async with Client(mcp) as client:
            result = await client.call_tool(
                "simulate_risk_check",
                {
                    "payload": {
                        "intent": _valid_intent_payload(),
                        "policy_override": bad_override,
                    },
                },
            )
        payload = _structured(result)
        assert payload["decision"] is None
        assert "policy_override" in payload["error"]

    @pytest.mark.asyncio
    async def test_malformed_intent_returns_error(self) -> None:
        mcp = _build_server()
        bad = _valid_intent_payload()
        del bad["size"]
        async with Client(mcp) as client:
            result = await client.call_tool(
                "simulate_risk_check",
                {
                    "payload": {
                        "intent": bad,
                        "policy_override": _valid_policy_payload(),
                    },
                },
            )
        payload = _structured(result)
        assert payload["decision"] is None
        assert "intent" in payload["error"]


# =========================== kill-switch tools ===============================


class TestKillSwitchTools:
    @pytest.mark.asyncio
    async def test_engage_calls_kill_switch_engage_with_reason(self) -> None:
        ks = _mock_kill_switch()
        mcp = _build_server(kill_switch=ks)
        async with Client(mcp) as client:
            result = await client.call_tool(
                "engage_kill_switch",
                {"reason": "manual"},
            )
        payload = _structured(result)
        assert payload["engaged"] is True
        assert payload["reason"] == "manual"
        ks.engage.assert_called_once_with(reason="manual")

    @pytest.mark.asyncio
    async def test_disengage_calls_kill_switch_disengage(self) -> None:
        ks = _mock_kill_switch()
        mcp = _build_server(kill_switch=ks)
        async with Client(mcp) as client:
            result = await client.call_tool("disengage_kill_switch", {})
        payload = _structured(result)
        assert payload["engaged"] is False
        assert payload["reason"] is None
        ks.disengage.assert_called_once()

    @pytest.mark.asyncio
    async def test_engage_empty_reason_raises_tool_error(self) -> None:
        # Pydantic `Field(min_length=1)` on the `reason` parameter rejects
        # empty strings at dispatch — FastMCP translates this into a
        # ToolError from the client side.
        ks = _mock_kill_switch()
        mcp = _build_server(kill_switch=ks)
        async with Client(mcp) as client:
            with pytest.raises(ToolError):
                await client.call_tool(
                    "engage_kill_switch",
                    {"reason": ""},
                )


# ======================== DTO-level coherence tests ==========================


class TestResponseCoherence:
    def test_set_rejects_error_and_id(self) -> None:
        with pytest.raises(ValidationError):
            SetRiskPolicyResponse(id="abc", note="x", error="boom")

    def test_set_rejects_success_without_id(self) -> None:
        with pytest.raises(ValidationError):
            SetRiskPolicyResponse(id=None, note="", error=None)

    def test_get_rejects_error_with_policy(self) -> None:
        # Build a valid payload so the coherence guard is actually reached.

        payload = RiskPolicyPayload(
            max_leverage=LimitDecimalPayload(value=Decimal("3"), severity=Severity.DENY),
            max_position_pct=LimitDecimalPayload(
                value=Decimal("0.25"),
                severity=Severity.DENY,
            ),
            max_daily_loss_pct=LimitDecimalPayload(
                value=Decimal("0.05"),
                severity=Severity.WARN,
            ),
            cooldown_after_n_losses=LimitIntPayload(value=3, severity=Severity.WARN),
            min_balance_buffer=LimitDecimalPayload(
                value=Decimal("100"),
                severity=Severity.DENY,
            ),
        )
        with pytest.raises(ValidationError):
            GetRiskPolicyResponse(id="abc", policy=payload, error="boom")

    def test_evaluate_rejects_error_with_decision(self) -> None:
        decision = RiskDecisionDTO.from_domain(_ok_decision())
        with pytest.raises(ValidationError):
            EvaluateTradeIntentResponse(decision=decision, error="boom")

    def test_simulate_rejects_success_without_decision(self) -> None:
        with pytest.raises(ValidationError):
            SimulateRiskCheckResponse(decision=None, policy_source="active", error=None)

    def test_kill_switch_status_accepts_engaged_pair(self) -> None:
        resp = KillSwitchStatusResponse(
            engaged=True,
            engaged_at_ms=1,
            reason="x",
        )
        assert resp.engaged is True
        assert resp.reason == "x"
