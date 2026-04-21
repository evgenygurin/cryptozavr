"""Test Domain → ToolError mapping."""

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
from cryptozavr.mcp.errors import domain_to_tool_error


class TestDomainToToolError:
    def test_symbol_not_found_maps_to_clear_message(self) -> None:
        exc = SymbolNotFoundError(user_input="XYZ-ABC", venue="kucoin")
        err = domain_to_tool_error(exc)
        assert isinstance(err, ToolError)
        assert "XYZ-ABC" in str(err)
        assert "kucoin" in str(err)

    def test_venue_not_supported_mentions_venue(self) -> None:
        exc = VenueNotSupportedError(venue="binance")
        err = domain_to_tool_error(exc)
        assert "binance" in str(err)

    def test_rate_limit_suggests_retry(self) -> None:
        exc = RateLimitExceededError("kucoin backoff")
        err = domain_to_tool_error(exc)
        assert "rate limit" in str(err).lower()

    def test_provider_unavailable_is_retriable(self) -> None:
        exc = ProviderUnavailableError("network")
        err = domain_to_tool_error(exc)
        assert "unavailable" in str(err).lower()

    def test_validation_error_preserves_message(self) -> None:
        exc = ValidationError("negative limit")
        err = domain_to_tool_error(exc)
        assert "negative limit" in str(err)

    def test_unknown_domain_error_falls_back_to_str(self) -> None:
        class _OddDomainError(DomainError):
            pass

        exc = _OddDomainError("weird")
        err = domain_to_tool_error(exc)
        assert "weird" in str(err)
