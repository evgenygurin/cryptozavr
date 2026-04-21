"""Map domain exceptions to fastmcp ToolError with user-facing messages."""

from __future__ import annotations

from fastmcp.exceptions import ToolError

from cryptozavr.domain.exceptions import (
    DomainError,
    ProviderUnavailableError,
    RateLimitExceededError,
    SymbolNotFoundError,
    ValidationError,
    VenueNotSupportedError,
)


def domain_to_tool_error(exc: DomainError) -> ToolError:
    """Convert a domain exception into a client-facing ToolError."""
    if isinstance(exc, SymbolNotFoundError):
        return ToolError(
            f"Symbol {exc.user_input!r} not found on venue {exc.venue!r}.",
        )
    if isinstance(exc, VenueNotSupportedError):
        return ToolError(
            f"Venue {exc.venue!r} is not supported by this server.",
        )
    if isinstance(exc, RateLimitExceededError):
        return ToolError(
            "Upstream rate limit exceeded. Please retry in a few seconds.",
        )
    if isinstance(exc, ProviderUnavailableError):
        return ToolError(
            "Upstream provider is unavailable. Please retry later.",
        )
    if isinstance(exc, ValidationError):
        return ToolError(f"Invalid input: {exc}")
    return ToolError(str(exc))
