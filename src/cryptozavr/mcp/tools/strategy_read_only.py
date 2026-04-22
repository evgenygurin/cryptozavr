"""Unit 2D-2 / 2E-1 read-only strategy tools: list / explain / diff.

`list_strategies` delegates to `StrategySpecRepository.list_recent()` — real
Supabase-backed persistence landed in 2E-1. `explain_strategy` renders a
human-readable markdown + structured sections view of a StrategySpec payload,
and `diff_strategies` produces JSON-pointer-style per-field diffs between two
payloads. Both are pure (no DI dependencies).

Payloads are validated via `StrategySpecPayload.model_validate`; bad input
is surfaced through coherent error fields on the response DTOs rather than
raised upward (MCP clients get a structured, maskable message either way).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import Context, FastMCP
from fastmcp.dependencies import Depends
from pydantic import Field, ValidationError

from cryptozavr.infrastructure.persistence.strategy_spec_repo import (
    StrategySpecRepository,
)
from cryptozavr.mcp.lifespan_state import get_strategy_spec_repo
from cryptozavr.mcp.tools.strategy_dtos import (
    ConditionPayload,
    DiffStrategiesResponse,
    ExplainStrategyResponse,
    ExplanationSectionDTO,
    FieldDiffDTO,
    IndicatorRefPayload,
    ListStrategiesResponse,
    StoredStrategySummaryDTO,
    StrategySpecPayload,
)

# Module-level singleton — avoids B008 (function call in default argument).
_STRATEGY_SPEC_REPO: StrategySpecRepository = Depends(get_strategy_spec_repo)


def _render_indicator(ref: IndicatorRefPayload) -> str:
    return f"{ref.kind.value.upper()}({ref.period}, {ref.source.value})"


def _render_condition(cond: ConditionPayload) -> str:
    lhs = _render_indicator(cond.lhs)
    rhs = (
        _render_indicator(cond.rhs) if isinstance(cond.rhs, IndicatorRefPayload) else str(cond.rhs)
    )
    return f"{lhs} {cond.op.value} {rhs}"


def _render_markdown(spec: StrategySpecPayload) -> str:
    entry_conds = " AND ".join(_render_condition(c) for c in spec.entry.conditions)
    exit_lines: list[str] = []
    if spec.exit.conditions:
        exit_lines.append(" OR ".join(_render_condition(c) for c in spec.exit.conditions))
    if spec.exit.take_profit_pct is not None:
        exit_lines.append(f"TP {spec.exit.take_profit_pct}")
    if spec.exit.stop_loss_pct is not None:
        exit_lines.append(f"SL {spec.exit.stop_loss_pct}")
    exit_text = " | ".join(exit_lines) if exit_lines else "(none)"
    return (
        f"# {spec.name}\n\n"
        f"{spec.description}\n\n"
        f"**Venue:** {spec.venue.value}  \n"
        f"**Symbol:** {spec.symbol.native_symbol}  \n"
        f"**Timeframe:** {spec.timeframe.value}\n\n"
        f"## Entry ({spec.entry.side.value.upper()})\n\n"
        f"{entry_conds}\n\n"
        f"## Exit\n\n"
        f"{exit_text}\n\n"
        f"## Risk\n\n"
        f"size_pct = {spec.size_pct}\n"
    )


def _render_sections(spec: StrategySpecPayload) -> list[ExplanationSectionDTO]:
    entry_conds = " AND ".join(_render_condition(c) for c in spec.entry.conditions)
    exit_parts: list[str] = []
    if spec.exit.conditions:
        exit_parts.append(" OR ".join(_render_condition(c) for c in spec.exit.conditions))
    if spec.exit.take_profit_pct is not None:
        exit_parts.append(f"TP {spec.exit.take_profit_pct}")
    if spec.exit.stop_loss_pct is not None:
        exit_parts.append(f"SL {spec.exit.stop_loss_pct}")
    return [
        ExplanationSectionDTO(
            title="Entry",
            body=f"side={spec.entry.side.value} when {entry_conds}",
        ),
        ExplanationSectionDTO(
            title="Exit",
            body=" | ".join(exit_parts) if exit_parts else "(none)",
        ),
        ExplanationSectionDTO(title="Risk", body=f"size_pct={spec.size_pct}"),
    ]


def _walk_diff(left: Any, right: Any, path: str) -> list[FieldDiffDTO]:
    if isinstance(left, dict) and isinstance(right, dict):
        keys = set(left.keys()) | set(right.keys())
        out: list[FieldDiffDTO] = []
        for k in sorted(keys):
            out.extend(_walk_diff(left.get(k), right.get(k), f"{path}/{k}"))
        return out
    if isinstance(left, list) and isinstance(right, list):
        out = []
        for i in range(max(len(left), len(right))):
            l_val = left[i] if i < len(left) else None
            r_val = right[i] if i < len(right) else None
            out.extend(_walk_diff(l_val, r_val, f"{path}/{i}"))
        return out
    if left != right:
        return [FieldDiffDTO(path=path or "/", left=left, right=right)]
    return []


def register_strategy_read_only_tools(mcp: FastMCP) -> None:
    """Attach list_strategies / explain_strategy / diff_strategies to mcp."""

    @mcp.tool(
        name="list_strategies",
        description=(
            "List persisted strategies ordered by created_at DESC (most recent "
            "first). Returns summaries (id, name, version, venue, symbol, "
            "timeframe, created/updated timestamps). On DB failure returns an "
            "empty list with `error` populated."
        ),
        tags={"strategy", "read-only", "phase-2"},
        timeout=30.0,
        annotations={
            "readOnlyHint": True,
            "idempotentHint": True,
            "destructiveHint": False,
        },
    )
    async def list_strategies(
        ctx: Context,
        limit: Annotated[
            int,
            Field(default=50, ge=1, le=500, description="Max rows to return."),
        ] = 50,
        repo: StrategySpecRepository = _STRATEGY_SPEC_REPO,
    ) -> ListStrategiesResponse:
        await ctx.info("list_strategies")
        try:
            rows = await repo.list_recent(limit=limit)
        except Exception as exc:
            return ListStrategiesResponse(
                strategies=[],
                error=f"repository error: {type(exc).__name__}: {exc}",
            )
        return ListStrategiesResponse(
            strategies=[
                StoredStrategySummaryDTO(
                    id=str(r.id),
                    name=r.name,
                    version=r.version,
                    venue=r.venue_id,
                    symbol_native=r.symbol_native,
                    timeframe=r.timeframe,
                    created_at_ms=r.created_at_ms,
                    updated_at_ms=r.updated_at_ms,
                )
                for r in rows
            ],
            error=None,
        )

    @mcp.tool(
        name="explain_strategy",
        description=(
            "Render a human-readable explanation of a StrategySpec payload. "
            "Returns markdown plus structured sections (Entry/Exit/Risk). On "
            "malformed input returns error only, leaving markdown/sections empty."
        ),
        tags={"strategy", "read-only", "phase-2"},
        timeout=30.0,
        annotations={
            "readOnlyHint": True,
            "idempotentHint": True,
            "destructiveHint": False,
        },
    )
    async def explain_strategy(
        spec: Annotated[
            dict[str, Any],
            Field(description="StrategySpec payload (raw JSON object)."),
        ],
        ctx: Context,
    ) -> ExplainStrategyResponse:
        await ctx.info("explain_strategy")
        try:
            payload = StrategySpecPayload.model_validate(spec)
        except ValidationError as exc:
            first = exc.errors()[0]
            loc = "/".join(str(p) for p in first["loc"]) or "<root>"
            msg = f"payload invalid at {loc}: {first['msg']}"
            return ExplainStrategyResponse(error=msg)
        return ExplainStrategyResponse(
            markdown=_render_markdown(payload),
            sections=_render_sections(payload),
        )

    @mcp.tool(
        name="diff_strategies",
        description=(
            "Diff two StrategySpec payloads. Returns a list of field-level "
            "differences with JSON-pointer-like paths "
            "(e.g. /entry/conditions/0/lhs/period). If either payload is "
            "malformed, returns errors only with equal=False."
        ),
        tags={"strategy", "read-only", "phase-2"},
        timeout=30.0,
        annotations={
            "readOnlyHint": True,
            "idempotentHint": True,
            "destructiveHint": False,
        },
    )
    async def diff_strategies(
        a: Annotated[
            dict[str, Any],
            Field(description="First StrategySpec payload."),
        ],
        b: Annotated[
            dict[str, Any],
            Field(description="Second StrategySpec payload."),
        ],
        ctx: Context,
    ) -> DiffStrategiesResponse:
        await ctx.info("diff_strategies")
        errors: list[str] = []
        payload_a: StrategySpecPayload | None = None
        payload_b: StrategySpecPayload | None = None
        try:
            payload_a = StrategySpecPayload.model_validate(a)
        except ValidationError as exc:
            errors.append(f"spec a: {exc.errors()[0]['msg']}")
        try:
            payload_b = StrategySpecPayload.model_validate(b)
        except ValidationError as exc:
            errors.append(f"spec b: {exc.errors()[0]['msg']}")
        if errors or payload_a is None or payload_b is None:
            return DiffStrategiesResponse(equal=False, differences=[], errors=errors)
        dump_a = payload_a.model_dump(mode="json")
        dump_b = payload_b.model_dump(mode="json")
        diffs = _walk_diff(dump_a, dump_b, path="")
        return DiffStrategiesResponse(equal=not diffs, differences=diffs)
