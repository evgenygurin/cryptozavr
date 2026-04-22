"""validate_strategy MCP tool — parse StrategySpec payload, return structured errors.

First phase-2D tool. Accepts the payload as a raw dict so pydantic's own
ValidationError (raised at the dispatch layer if we typed the arg as the
payload model) does not short-circuit the tool body. The tool then:

1. Parses the dict via `StrategySpecPayload.model_validate` — catches
   field-shape errors (missing fields, bad enums, range violations).
2. Calls `payload.to_domain()` — catches domain-level errors surfaced by
   Symbol.__post_init__ and the domain StrategySpec model_validator
   (e.g. StrategyExit bail-out invariant).

In both failure paths a structured `ValidateStrategyResponse` is returned
with `valid=False` and a flat list of issues. Pydantic `ValidationError`
details map to `ValidationIssueDTO`; domain `ValueError` / `ValidationError`
become a single `value_error` issue at the root location.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import Context, FastMCP
from pydantic import Field, ValidationError

from cryptozavr.domain.exceptions import ValidationError as DomainValidationError
from cryptozavr.mcp.tools.strategy_dtos import (
    StrategySpecPayload,
    ValidateStrategyResponse,
    ValidationIssueDTO,
)


def _issues_from_pydantic(exc: ValidationError) -> list[ValidationIssueDTO]:
    return [
        ValidationIssueDTO(
            location=list(err["loc"]),
            message=str(err["msg"]),
            type=str(err["type"]),
        )
        for err in exc.errors()
    ]


def register_validate_strategy_tool(mcp: FastMCP) -> None:
    """Attach the validate_strategy tool to the given FastMCP instance."""

    @mcp.tool(
        name="validate_strategy",
        description=(
            "Validate a StrategySpec payload without executing it. "
            "Returns valid=True if the payload parses into a domain StrategySpec, "
            "otherwise valid=False with a structured list of issues "
            "(pydantic field errors and domain invariant violations)."
        ),
        tags={"strategy", "validation", "read-only", "phase-2"},
        annotations={
            "readOnlyHint": True,
            "idempotentHint": True,
            "destructiveHint": False,
        },
    )
    async def validate_strategy(
        spec: Annotated[
            dict[str, Any],
            Field(description="StrategySpec payload (raw JSON object)."),
        ],
        ctx: Context,
    ) -> ValidateStrategyResponse:
        name_hint = spec.get("name") if isinstance(spec, dict) else None
        await ctx.info(f"validate_strategy name={name_hint!r}")

        # Phase 1 — payload shape.
        try:
            payload = StrategySpecPayload.model_validate(spec)
        except ValidationError as exc:
            return ValidateStrategyResponse(valid=False, issues=_issues_from_pydantic(exc))

        # Phase 2 — domain construction.
        try:
            payload.to_domain()
        except ValidationError as exc:
            return ValidateStrategyResponse(valid=False, issues=_issues_from_pydantic(exc))
        except (DomainValidationError, ValueError) as exc:
            return ValidateStrategyResponse(
                valid=False,
                issues=[
                    ValidationIssueDTO(location=[], message=str(exc), type="value_error"),
                ],
            )

        return ValidateStrategyResponse(valid=True, issues=[])
