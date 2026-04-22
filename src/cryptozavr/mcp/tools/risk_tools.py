"""MCP tool module — six risk tools wired over RiskEngine + repo + KillSwitch.

Payloads arrive as raw `dict[str, Any]` so malformed input surfaces as a
structured `error` envelope instead of a pydantic ValidationError at
dispatch time.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastmcp import Context, FastMCP
from fastmcp.dependencies import Depends
from pydantic import Field, ValidationError

from cryptozavr.application.risk.engine import RiskEngine
from cryptozavr.application.risk.kill_switch import KillSwitch
from cryptozavr.domain.exceptions import ValidationError as DomainValidationError
from cryptozavr.infrastructure.persistence.risk_policy_repo import (
    RiskPolicyRepository,
)
from cryptozavr.mcp.lifespan_state import (
    get_kill_switch,
    get_risk_engine,
    get_risk_policy_repo,
)
from cryptozavr.mcp.tools.risk_dtos import (
    EvaluateTradeIntentResponse,
    GetRiskPolicyResponse,
    KillSwitchStatusResponse,
    RiskDecisionDTO,
    RiskPolicyPayload,
    SetRiskPolicyResponse,
    SimulateRiskCheckResponse,
    TradeIntentPayload,
)

_LOGGER = logging.getLogger(__name__)

# Module-level singletons — avoid B008 (function call in default argument).
_RISK_ENGINE: RiskEngine = Depends(get_risk_engine)
_KILL_SWITCH: KillSwitch = Depends(get_kill_switch)
_RISK_POLICY_REPO: RiskPolicyRepository = Depends(get_risk_policy_repo)


# --------------------------- tool impl (module-level) ------------------------


async def _set_risk_policy_impl(
    policy: dict[str, Any],
    ctx: Context,
    repo: RiskPolicyRepository,
) -> SetRiskPolicyResponse:
    await ctx.info("set_risk_policy")
    try:
        payload = RiskPolicyPayload.model_validate(policy)
    except ValidationError as exc:
        first = exc.errors()[0]
        loc = "/".join(str(p) for p in first["loc"]) or "<root>"
        return SetRiskPolicyResponse(
            id=None,
            note="",
            error=f"policy invalid at {loc}: {first['msg']}",
        )
    try:
        domain_policy = payload.to_domain()
    except (ValidationError, ValueError) as exc:
        return SetRiskPolicyResponse(
            id=None,
            note="",
            error=f"policy domain invalid: {exc}",
        )
    try:
        policy_id = await repo.save_and_activate(domain_policy)
    except Exception as exc:
        # Broad except: pg pool / network / trigger failures all surface as
        # a single wire-format error line; traceback goes to stderr via logging.
        _LOGGER.exception("risk_policy repo save_and_activate crashed: %s", exc)
        await ctx.error(f"set_risk_policy repo failure: {type(exc).__name__}")
        return SetRiskPolicyResponse(
            id=None,
            note="",
            error=f"repository error: {type(exc).__name__}: {exc}",
        )
    return SetRiskPolicyResponse(
        id=str(policy_id),
        note="saved and activated",
        error=None,
    )


async def _get_risk_policy_impl(
    ctx: Context,
    repo: RiskPolicyRepository,
) -> GetRiskPolicyResponse:
    await ctx.info("get_risk_policy")
    try:
        row = await repo.get_active()
    except Exception as exc:
        _LOGGER.exception("risk_policy repo get_active crashed: %s", exc)
        await ctx.error(f"get_risk_policy repo failure: {type(exc).__name__}")
        return GetRiskPolicyResponse(
            error=f"repository error: {type(exc).__name__}: {exc}",
        )
    if row is None:
        return GetRiskPolicyResponse(
            id=None,
            policy=None,
            note="no active risk policy — set one via set_risk_policy",
        )
    # Repo returns a domain RiskPolicy; mirror back to the wire payload shape.
    payload = RiskPolicyPayload.model_validate(row.policy.model_dump(mode="json"))
    return GetRiskPolicyResponse(
        id=str(row.id),
        policy=payload,
        activated_at_ms=row.activated_at_ms,
        note="active",
    )


async def _evaluate_trade_intent_impl(
    intent: dict[str, Any],
    ctx: Context,
    engine: RiskEngine,
    repo: RiskPolicyRepository,
) -> EvaluateTradeIntentResponse:
    await ctx.info("evaluate_trade_intent")
    try:
        intent_payload = TradeIntentPayload.model_validate(intent)
    except ValidationError as exc:
        first = exc.errors()[0]
        loc = "/".join(str(p) for p in first["loc"]) or "<root>"
        return EvaluateTradeIntentResponse(
            error=f"intent invalid at {loc}: {first['msg']}",
        )
    try:
        domain_intent = intent_payload.to_domain()
    except (DomainValidationError, ValueError) as exc:
        return EvaluateTradeIntentResponse(
            error=f"intent domain invalid: {exc}",
        )
    try:
        row = await repo.get_active()
    except Exception as exc:
        _LOGGER.exception("evaluate_trade_intent repo failure: %s", exc)
        await ctx.error(f"evaluate_trade_intent repo failure: {type(exc).__name__}")
        return EvaluateTradeIntentResponse(
            error=f"repository error: {type(exc).__name__}: {exc}",
        )
    if row is None:
        return EvaluateTradeIntentResponse(
            error="no active risk policy — set one via set_risk_policy",
        )
    try:
        decision = engine.evaluate(domain_intent, row.policy)
    except Exception as exc:
        _LOGGER.exception("RiskEngine.evaluate crashed: %s", exc)
        await ctx.error(f"evaluate_trade_intent engine failure: {type(exc).__name__}")
        return EvaluateTradeIntentResponse(
            error=f"engine error: {type(exc).__name__}: {exc}",
        )
    return EvaluateTradeIntentResponse(decision=RiskDecisionDTO.from_domain(decision))


async def _resolve_simulation_policy(
    payload: dict[str, Any],
    ctx: Context,
    repo: RiskPolicyRepository,
) -> tuple[Any, str, str | None]:
    """Return (policy, policy_source, error). Exactly one of policy/error is set.

    When `policy_override` is supplied, parse it and tag the source as
    ``"override"``. Otherwise fall back to the active policy from the repo;
    if none exists or the repo raises, return a structured error string.
    """
    override_raw = payload.get("policy_override")
    if override_raw is not None:
        if not isinstance(override_raw, dict):
            return None, "override", "policy_override must be an object"
        try:
            domain_policy = RiskPolicyPayload.model_validate(override_raw).to_domain()
        except (ValidationError, ValueError) as exc:
            return None, "override", f"policy_override invalid: {exc}"
        return domain_policy, "override", None
    try:
        row = await repo.get_active()
    except Exception as exc:
        _LOGGER.exception("simulate_risk_check repo failure: %s", exc)
        await ctx.error(f"simulate_risk_check repo failure: {type(exc).__name__}")
        return None, "active", f"repository error: {type(exc).__name__}: {exc}"
    if row is None:
        return None, "active", "no active risk policy — pass policy_override or set one"
    return row.policy, "active", None


async def _simulate_risk_check_impl(
    payload: dict[str, Any],
    ctx: Context,
    engine: RiskEngine,
    repo: RiskPolicyRepository,
) -> SimulateRiskCheckResponse:
    await ctx.info("simulate_risk_check")
    intent_raw = payload.get("intent")
    if not isinstance(intent_raw, dict):
        return SimulateRiskCheckResponse(error="payload.intent must be an object")
    try:
        domain_intent = TradeIntentPayload.model_validate(intent_raw).to_domain()
    except (ValidationError, DomainValidationError, ValueError) as exc:
        return SimulateRiskCheckResponse(error=f"intent invalid: {exc}")

    domain_policy, policy_source, policy_error = await _resolve_simulation_policy(
        payload,
        ctx,
        repo,
    )
    if policy_error is not None:
        return SimulateRiskCheckResponse(error=policy_error)
    assert domain_policy is not None  # coherence: no error → policy present
    try:
        decision = engine.evaluate(domain_intent, domain_policy)
    except Exception as exc:
        _LOGGER.exception("RiskEngine.evaluate (simulate) crashed: %s", exc)
        await ctx.error(f"simulate_risk_check engine failure: {type(exc).__name__}")
        return SimulateRiskCheckResponse(
            error=f"engine error: {type(exc).__name__}: {exc}",
        )
    return SimulateRiskCheckResponse(
        decision=RiskDecisionDTO.from_domain(decision),
        policy_source=policy_source,
    )


async def _engage_kill_switch_impl(
    reason: str,
    ctx: Context,
    kill_switch: KillSwitch,
) -> KillSwitchStatusResponse:
    await ctx.info(f"engage_kill_switch: {reason}")
    status = kill_switch.engage(reason=reason)
    return KillSwitchStatusResponse(
        engaged=status.engaged,
        engaged_at_ms=status.engaged_at_ms,
        reason=status.reason,
    )


async def _disengage_kill_switch_impl(
    ctx: Context,
    kill_switch: KillSwitch,
) -> KillSwitchStatusResponse:
    await ctx.info("disengage_kill_switch")
    status = kill_switch.disengage()
    return KillSwitchStatusResponse(
        engaged=status.engaged,
        engaged_at_ms=status.engaged_at_ms,
        reason=status.reason,
    )


# --------------------------- registration ------------------------------------


def register_risk_tools(mcp: FastMCP) -> None:
    """Attach the six risk tools to `mcp`."""

    @mcp.tool(
        name="set_risk_policy",
        description=(
            "Persist and activate a RiskPolicy. Inserts a new row; idempotent "
            "by BLAKE2b content_hash (re-saving the same policy returns the "
            "existing id). Save + activation run in one transaction — partial "
            "failure never leaves an orphan row. "
            "Note: max_daily_loss_pct is currently stored but not enforced by "
            "any handler."
        ),
        tags={"risk", "phase-3"},
        timeout=30.0,
        annotations={
            "readOnlyHint": False,
            "idempotentHint": True,
            "destructiveHint": False,
        },
    )
    async def set_risk_policy(
        policy: Annotated[
            dict[str, Any],
            Field(description="RiskPolicy payload (raw JSON object)."),
        ],
        ctx: Context,
        repo: RiskPolicyRepository = _RISK_POLICY_REPO,
    ) -> SetRiskPolicyResponse:
        return await _set_risk_policy_impl(policy, ctx, repo)

    @mcp.tool(
        name="get_risk_policy",
        description=(
            "Return the currently active RiskPolicy, or a note explaining that "
            "no policy is active yet."
        ),
        tags={"risk", "read-only", "phase-3"},
        timeout=10.0,
        annotations={
            "readOnlyHint": True,
            "idempotentHint": True,
            "destructiveHint": False,
        },
    )
    async def get_risk_policy(
        ctx: Context,
        repo: RiskPolicyRepository = _RISK_POLICY_REPO,
    ) -> GetRiskPolicyResponse:
        return await _get_risk_policy_impl(ctx, repo)

    @mcp.tool(
        name="evaluate_trade_intent",
        description=(
            "Run the RiskEngine chain against a TradeIntent using the "
            "currently active RiskPolicy. Returns a structured RiskDecision "
            "with per-handler violations. Requires an active policy — returns "
            "an error envelope otherwise."
        ),
        tags={"risk", "read-only", "phase-3"},
        timeout=10.0,
        annotations={
            "readOnlyHint": True,
            "idempotentHint": False,
            "destructiveHint": False,
        },
    )
    async def evaluate_trade_intent(
        intent: Annotated[
            dict[str, Any],
            Field(description="TradeIntent payload (raw JSON object)."),
        ],
        ctx: Context,
        engine: RiskEngine = _RISK_ENGINE,
        repo: RiskPolicyRepository = _RISK_POLICY_REPO,
    ) -> EvaluateTradeIntentResponse:
        return await _evaluate_trade_intent_impl(intent, ctx, engine, repo)

    @mcp.tool(
        name="simulate_risk_check",
        description=(
            "Same as evaluate_trade_intent but accepts an optional "
            "policy_override. If override is provided, it is used for this "
            "call only and NEVER persisted. If omitted, falls back to the "
            "currently active policy."
        ),
        tags={"risk", "read-only", "phase-3"},
        timeout=10.0,
        annotations={
            "readOnlyHint": True,
            "idempotentHint": False,
            "destructiveHint": False,
        },
    )
    async def simulate_risk_check(
        payload: Annotated[
            dict[str, Any],
            Field(
                description=(
                    "Simulation payload: {intent, policy_override?}. "
                    "policy_override overrides the active policy for this "
                    "call only. Omit to use the active policy."
                ),
            ),
        ],
        ctx: Context,
        engine: RiskEngine = _RISK_ENGINE,
        repo: RiskPolicyRepository = _RISK_POLICY_REPO,
    ) -> SimulateRiskCheckResponse:
        return await _simulate_risk_check_impl(payload, ctx, engine, repo)

    @mcp.tool(
        name="engage_kill_switch",
        description=(
            "Engage the runtime kill switch. All subsequent evaluate / "
            "simulate calls will return a DENY decision with a KillSwitch "
            "violation. State is runtime-only — server restart disengages."
        ),
        tags={"risk", "phase-3"},
        timeout=30.0,
        annotations={
            "readOnlyHint": False,
            "idempotentHint": True,
            "destructiveHint": False,
        },
    )
    async def engage_kill_switch(
        reason: Annotated[
            str,
            Field(min_length=1, description="Why the switch is engaged."),
        ],
        ctx: Context,
        kill_switch: KillSwitch = _KILL_SWITCH,
    ) -> KillSwitchStatusResponse:
        return await _engage_kill_switch_impl(reason, ctx, kill_switch)

    @mcp.tool(
        name="disengage_kill_switch",
        description="Disengage the runtime kill switch.",
        tags={"risk", "phase-3"},
        timeout=30.0,
        annotations={
            "readOnlyHint": False,
            "idempotentHint": True,
            "destructiveHint": False,
        },
    )
    async def disengage_kill_switch(
        ctx: Context,
        kill_switch: KillSwitch = _KILL_SWITCH,
    ) -> KillSwitchStatusResponse:
        return await _disengage_kill_switch_impl(ctx, kill_switch)
